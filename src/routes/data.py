from fastapi import FastAPI, APIRouter, Depends, UploadFile, status, Request, File, HTTPException
from fastapi.responses import JSONResponse
import os
import asyncio
from pathlib import Path

from src.helpers.config import get_settings, Settings

from src.controllers import DataController, ProjectController
from src.models.db_schemes.cv_analysis_db.db_tables import Asset, Project
from src.models.crud.AssetCrud import AssetCrud
from src.models.crud.ProjectCrud import ProjectCrud
from src.models.enums.AssetTypeEnum import AssetTypeEnum

from src.models.enums.DataBaseEnum import DataBaseEnum
from src.database import get_utils

import aiofiles
from src.models import ResponseSignal
import logging
from typing import List

logger = logging.getLogger('uvicorn.error')

data_router = APIRouter(
    prefix="/api/v1/data",
    tags=["api_v1", "data"],
)


async def process_single_file(file: UploadFile, project_id: int, project, asset_crud: AssetCrud, 
                             data_controller: DataController, app_settings: Settings) -> dict:
    """
    Process a single file - validate, upload to filesystem, and create database record.
    
    Args:
        file: The uploaded file object
        project_id: ID of the project
        project: The project document
        asset_crud: Database model for assets
        data_controller: Controller for data operations
        app_settings: Application settings
        
    Returns:
        dict: Result of the processing containing success status and metadata
    """
    

    # Secure filename processing
    filename = Path(file.filename).name
    
    # Validate the file properties (type and initial size check)
    is_valid, result_signal = data_controller.validate_uploaded_file(file=file)

    if not is_valid:
        await file.close()
        return {
            "filename": filename,
            "success": False,
            "error": result_signal,
            "file_id": None,
            "asset_id": None
        }

    file_path, file_id = data_controller.generate_unique_filepath(
        orig_file_name=filename,
        project_id=str(project_id)
    )

    try:

        # Upload file to filesystem with size monitoring

        size = 0
        async with aiofiles.open(file_path, "wb") as f:
            while chunk := await file.read(app_settings.FILE_DEFAULT_CHUNK_SIZE):
                size += len(chunk)
                # Runtime size validation
                if size > app_settings.FILE_MAX_SIZE * 1048576: # MB to bytes
                    raise ValueError(ResponseSignal.FILE_SIZE_EXCEEDED.value)
                await f.write(chunk)
        
        # Store the file metadata in the database
        
        asset_record = await asset_crud.create_asset(
            project_id=project_id,
            asset_type=AssetTypeEnum.FILE.value,
            asset_name=file_id,
            asset_size=size
        )

        return {
            "filename": filename,
            "success": True,
            "file_id": file_id,
            "asset_id": str(asset_record.asset_project_id) if asset_record else None
        }
        
    except ValueError as ve:
        logger.error(f"Validation error for {filename}: {ve}")
        if os.path.exists(file_path):
            os.remove(file_path)
        return {
            "filename": filename,
            "success": False,
            "error": str(ve),
            "file_id": file_id,
            "asset_id": None
        }
    except Exception as e:
        logger.error(f"Unexpected error uploading {filename}: {e}")
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as cleanup_error:
                logger.error(f"Cleanup failed for {file_path}: {cleanup_error}")
            
        return {
            "filename": filename,
            "success": False,
            "error": ResponseSignal.FILE_UPLOAD_FAILED.value,
            "file_id": file_id,
            "asset_id": None
        }
    finally:
        await file.close()




@data_router.post("/upload/{project_id}")
async def upload_data(
    request: Request, 
    project_id: int, 
    files: List[UploadFile] = File(..., description="List of files to upload"),
    app_settings: Settings = Depends(get_settings)
):
    """
    Upload multiple files concurrently for a specific project.
    
    - Validates project existence
    - Processes files in parallel using asyncio.gather
    - Performs size and extension validation
    - Returns detailed results for each file
    - Supports multi-status responses for partial successes
    """


    (db_engine, db_client_sessionmaker) = get_utils()


    # Instantiate models
    project_crud = ProjectCrud(db_client=db_client_sessionmaker)
   
    asset_crud = AssetCrud(db_client=db_client_sessionmaker)

    # Verify project exists
    project = await project_crud.get_project_or_create_one(project_id=project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found"
        )

    # Initialize controllers
    data_controller = DataController()
    project_controller = ProjectController()
    
    # Ensure project directory exists
    project_dir_path = project_controller.get_project_path(project_id=str(project_id))
    os.makedirs(project_dir_path, exist_ok=True)

    # Process files concurrently
    tasks = [
        process_single_file(
            file=file,
            project_id=project_id,
            project=project,
            asset_crud=asset_crud,
            data_controller=data_controller,
            app_settings=app_settings
        )
        for file in files
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Process results and handle exceptions
    processed_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(f"Task exception for {files[i].filename}: {result}")
            processed_results.append({
                "filename": files[i].filename,
                "success": False,
                "error": str(result),
                "file_id": None,
                "asset_id": None
            })
        else:
            processed_results.append(result)

    # Summary statistics
    uploaded_count = sum(1 for r in processed_results if r['success'])
    failed_count = len(processed_results) - uploaded_count
    db_inserted_count = sum(1 for r in processed_results if r['success'] and r['asset_id'])

    response_content = {
        "signal": ResponseSignal.FILE_UPLOAD_SUCCESS.value if uploaded_count > 0 else ResponseSignal.FILE_UPLOAD_FAILED.value,
        "uploaded_files": uploaded_count,
        "non_uploaded_files": failed_count,
        "inserted_files_db": db_inserted_count,
        "non_inserted_files_db": uploaded_count - db_inserted_count,
        "details": processed_results,
    }

    # Determine status code
    if uploaded_count == len(processed_results):
        return JSONResponse(status_code=status.HTTP_200_OK, content=response_content)
    elif uploaded_count == 0:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content=response_content)
    else:
        return JSONResponse(status_code=status.HTTP_207_MULTI_STATUS, content=response_content)

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
from src.models.crud.DataChunkCrud import DataChunkCrud
from src.models.enums.AssetTypeEnum import AssetTypeEnum

from src.models.enums.DataBaseEnum import DataBaseEnum
from src.database import get_utils

import aiofiles
from src.models.enums.ResponseEnums import ResponseSignal
import logging
from typing import List
from src.routes.schemes.data_schemes import ProcessRequest
from src.controllers.ProcessController import ProcessController



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
            "file_name": None,
            "asset_id": None
        }

    file_path, file_name = data_controller.generate_unique_filepath(
        orig_file_name=filename,
        project_id=str(project_id)
    )

    try:

        # Upload file to filesystem with size monitoring

        size = 0
        async with aiofiles.open(file_path, "wb") as f:
            while chunk := await file.read(app_settings.FILE_DEFAULT_CHUNK_SIZE_FOR_UPLOAD):
                size += len(chunk)
                # Runtime size validation
                if size > app_settings.FILE_MAX_SIZE * 1048576: # MB to bytes
                    raise ValueError(ResponseSignal.FILE_SIZE_EXCEEDED.value)
                await f.write(chunk)
        
        # Store the file metadata in the database
        
        asset_record = await asset_crud.create_asset(
            project_id=project_id,
            asset_type=AssetTypeEnum.FILE.value,
            asset_name=file_name,
            asset_size=size
        )

        return {
            "filename": filename,
            "success": True,
            "file_name": file_name,
            "asset_id": str(asset_record.asset_id) if asset_record else None
        }
        
    except ValueError as ve:
        logger.error(f"Validation error for {filename}: {ve}")
        if os.path.exists(file_path):
            os.remove(file_path)
        return {
            "filename": filename,
            "success": False,
            "error": str(ve),
            "file_name": file_name,
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
            "file_name": file_name,
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


    (db_engine, db_client_sessionmaker) = await get_utils()


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
    Path(project_dir_path).mkdir(parents=True, exist_ok=True)

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
                "file_name": None,
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


#------------------
# Process Endpoint
#------------------

@data_router.post("/process/{project_id}")
async def process_endpoint( project_id: int, process_request: ProcessRequest):
    """
    Process endpoint for a specific project.
    - split all project files into chunks or single file if file_name is provided
    - input : {project_id, file_name, chunk_size, overlap_size, do_reset}
    """

    #get variables : 
    file_name = process_request.file_name
    chunk_size = process_request.chunk_size
    overlap_size = process_request.overlap_size
    do_reset = process_request.do_reset

    (db_engine, db_client_sessionmaker) = await get_utils()

    #instialize object 
    process_controller = ProcessController(str(project_id))

    asset_crud = AssetCrud(db_client= db_client_sessionmaker)
    chunk_crud = DataChunkCrud(db_client= db_client_sessionmaker)


    #----------------------------------------logic-------------------------------------------------

    project_files_ids = {}

    # delete all chunks in our DB  :
    if do_reset:
        _ = await chunk_crud.delete_chunks_by_project(project_id=project_id)


    # 	If a file_name is provided, it fetches that single asset record from the database
    if file_name:
        asset_record = await asset_crud.get_asset_by_name(
            asset_name=file_name,
            project_id=project_id
        )

        if asset_record is None:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "signal": ResponseSignal.FILE_NAME_ERROR.value,
                }
            )

        project_files_ids = {asset_record.asset_name: asset_record.asset_id}
        
    # get all assets in table Asset for project_id
    else:
        
        project_files = await asset_crud.get_assets_by_project(
            project_id=project_id
        )

        project_files_ids = {record.asset_name: record.asset_id for record in project_files}

    no_files_to_process = len(project_files_ids)

    # For each file, it loads the file content, splits it into chunks, and inserts the chunks into the database
    no_chunks = 0
    no_files_processed = 0
    for file_name, asset_id in project_files_ids.items():
        file_content = process_controller.load_documents(file_name)

        if file_content is None:
            no_files_processed += 1
            continue

        file_chunks = process_controller.split_documents(file_content, chunk_size, overlap_size)

        # file_chunks is None : no object returned from split_documents
        # len(file_chunks) == 0 : list of chunks is empty  ==> object created but no chunks
        if file_chunks is None or len(file_chunks) == 0:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "signal": ResponseSignal.PROCESSING_FAILED.value,
                }
            )
            
        no_chunks += len(file_chunks) 
        no_files_processed += 1

        # Prepare batch insertion
        chunks_to_insert = [
            {
                "text": chunk.page_content,
                "order": i + 1,
                "metadata": chunk.metadata
            }
            for i, chunk in enumerate(file_chunks)
        ]

        try:
            # Insert chunks in batch
            await chunk_crud.create_chunks_batch(
                project_id=project_id,
                asset_id=asset_id,
                chunks_data=chunks_to_insert
            )
        except Exception as e:
            logger.error(f"Error inserting chunks for asset {asset_id} in project {project_id}: {e}")
            # If one file fails, we continue with the others instead of crashing the whole request
            continue

    return JSONResponse(
        content={
            "signal": ResponseSignal.PROCESSING_SUCCESS.value,
            "inserted_chunks": no_chunks,
            "processed_files": no_files_processed,
            "total_files": no_files_to_process,
        }
    )
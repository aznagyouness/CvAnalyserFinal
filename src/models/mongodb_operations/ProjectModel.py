from .BaseDataModel import BaseDataModel
from .db_schemes import Project
from .enums.DataBaseEnum import DataBaseEnum

class ProjectModel(BaseDataModel):

    def __init__(self, db_client: object):
        super().__init__(db_client=db_client)
        self.collection = self.db_client[DataBaseEnum.COLLECTION_PROJECT_NAME.value]

    async def ensure_indexes(self):
        """Create indexes defined in Project model (idempotent operation)"""
        for index in Project.get_indexes():
            await self.collection.create_index(
                index["key"],
                name=index["name"],
                unique=index["unique"]
            )

    # we seprate the creation of the instance and the initialization of the collection by creating index because
    # __init__ is a synchronous method and ensure_indexes is an asynchronous method
    # this allows us to create the instance and then call ensure_indexes asynchronously
    @classmethod
    async def create_instance(cls, db_client: object):
        instance = cls(db_client)
        await instance.ensure_indexes()
        return instance
    
    # ---------------insert project document with project_id guaranteed to be unique ---------------------------------:
    async def insert_one_project_document(self, project: Project):
        """Insert project without duplicate checking (since project_id is guaranteed unique)"""
        result = await self.collection.insert_one(
            project.dict(by_alias=True, exclude_unset=True)      # you can remove by_alias=True since Pydantic will automatically handle the id ↔ _id mapping (and similar cases) without requiring explicit alias conversion.
        )                                                        # exclude_unset=True : Excludes fields that were not provided (keeping only user-assigned values), so any non value provided fields will not be included in the database document. ==> save memory + avoid non provided values.
        project.id = result.inserted_id                          # after insertion, we can set the id (=None) field of the project instance to the inserted_id returned by MongoDB
        return project

    # --------------------retun existing project document or insert a new one if it does not exist ------------:
    async def get_or_insert_one_project_document(self, project_id: str):
        """Get existing project or create new one"""
        if record := await self.collection.find_one({"project_id": project_id}):
            return Project(**record)
        
        return await self.insert_one_project_document(Project(project_id=project_id))

    # --------------get all project documents with pagination-----------------------------------:
    async def get_all_project_documents(self, page: int = 1, page_size: int = 10):     # Danger: Loads ALL documents into memory! 1M docs? RIP.
        """Paginated project retrieval"""
        total_documents = await self.collection.count_documents({})
        total_pages = (total_documents + page_size - 1) // page_size       # (51-1+10)//10 = 6   and   (50-1+10)//10 = 5

        cursor = self.collection.find().skip((page - 1) * page_size).limit(page_size)       # (e.g., page 2 skips the first page_size docs) & limit(page_size) Restricts results to the current page’s chunk (e.g., 10 docs per page).
        projects = [Project(**doc) async for doc in cursor]                                 # async for allows us to iterate over the cursor asynchronously, yielding Project instances for each document.

        return projects, total_pages
    
    
"""
from .BaseDataModel import BaseDataModel
from .db_schemes import Project
from .enums.DataBaseEnum import DataBaseEnum

class ProjectModel(BaseDataModel):

    def __init__(self, db_client: object):
        super().__init__(db_client=db_client)
        self.collection = self.db_client[DataBaseEnum.COLLECTION_PROJECT_NAME.value]

    @classmethod
    async def create_instance(cls, db_client: object):
        instance = cls(db_client)
        await instance.init_collection()
        return instance

    async def init_collection(self):
        all_collections = await self.db_client.list_collection_names()
        if DataBaseEnum.COLLECTION_PROJECT_NAME.value not in all_collections:
            self.collection = self.db_client[DataBaseEnum.COLLECTION_PROJECT_NAME.value]
            indexes = Project.get_indexes()
            for index in indexes:
                await self.collection.create_index(
                    index["key"],
                    name=index["name"],
                    unique=index["unique"]
                )


    async def create_project(self, project: Project):

        result = await self.collection.insert_one(project.dict(by_alias=True, exclude_unset=True))
        project.id = result.inserted_id

        return project

    async def get_project_or_create_one(self, project_id: str):

        record = await self.collection.find_one({
            "project_id": project_id
        })

        if record is None:
            # create new project
            project = Project(project_id=project_id)
            project = await self.create_project(project=project)

            return project
        
        return Project(**record)

    async def get_all_projects(self, page: int=1, page_size: int=10):

        # count total number of documents
        total_documents = await self.collection.count_documents({})

        # calculate total number of pages
        total_pages = total_documents // page_size
        if total_documents % page_size > 0:
            total_pages += 1

        cursor = self.collection.find().skip( (page-1) * page_size ).limit(page_size)
        projects = []
        async for document in cursor:
            projects.append(
                Project(**document)
            )

        return projects, total_pages
"""
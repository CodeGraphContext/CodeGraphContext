# src/codegraphcontext/api/schemas.py
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional

class IndexRequest(BaseModel):
    path: str = Field(..., description="Local path to the repository or file to index")
    repo_name: Optional[str] = Field(None, description="Optional name for the repository")
    branch: str = "main"
    force: bool = False

class QueryRequest(BaseModel):
    query: str = Field(..., description="Cypher query to execute")
    params: Dict[str, Any] = Field(default_factory=dict, description="Parameters for the query")

class SearchRequest(BaseModel):
    query: str = Field(..., description="Search query")
    top_k: int = 10

class ToolCallRequest(BaseModel):
    name: str = Field(..., description="Name of the MCP tool to call")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Arguments for the tool")

class ApiResponse(BaseModel):
    status: str
    message: Optional[str] = None
    data: Optional[Any] = None
    error: Optional[str] = None

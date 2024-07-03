from pydantic import BaseModel, Field

#
# We use PyDantic and Instructor in combination with a LLM to find attributes and turn them into structured data.
#

# Attributes relative to source code
class Attributes(BaseModel):
    """Code attributes of the file"""
    language: str = Field(..., description = "What is the coding language")
    function_count: int = Field(..., description = "Count the amount of functions definitions")
    functions: list[str] = Field(..., description = "A list of function definitions while including the parameters")
    classes_count: int = Field(..., description = "Count the amount of classes defined")
    classes: list[str] = Field(..., description = "A list of class definitions while including the constructors")
    dependencies: list[str] = Field(..., description = "A list of all depencies used for this file")
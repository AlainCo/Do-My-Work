from pydantic import BaseModel, ConfigDict, Field


class HelloJobConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    app_name: str = Field(default="Do My Work")
    greeting: str = Field(default="Hello")
    target: str = Field(default="world")


class HelloJobResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    app_name: str
    message: str
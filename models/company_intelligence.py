from pydantic import BaseModel
from typing import List, Optional


class SocialProfile(BaseModel):

    platform:str

    username:Optional[str]=None

    url:Optional[str]=None

    followers:int=0

    verified:bool=False


class WebsiteInformation(BaseModel):

    url:str

    title:str=""

    description:str=""

    products:List[str]=[]

    services:List[str]=[]

    pricing_model:Optional[str]=None

    industries:List[str]=[]

    audience:List[str]=[]

    technologies:List[str]=[]

    keywords:List[str]=[]


class SearchInformation(BaseModel):

    source:str

    title:str

    url:str

    snippet:str

    score:float


class CompanyIntelligence(BaseModel):

    name:str

    confidence:float=0

    website:Optional[WebsiteInformation]=None

    search_results:List[SearchInformation]=[]

    socials:List[SocialProfile]=[]

    competitors:List[str]=[]

    reasoning:str=""
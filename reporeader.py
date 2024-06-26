from github import Github
from github import Auth
from github import Repository
from github import ContentFile

class RepoReader():

    def __init__(self, token='', repo=''):
        self.github_token = token
        self.github_repo_name = repo        
        self.github_handle = None     
        self.github_repo = None   

    def connect(self, token: str):
        self.github_token = token

        # using an access token to connect
        auth = Auth.Token(self.github_token)

        # Get the GitHub handle
        self.github_handle = Github(auth=auth)

    def setRepository(self, repo: str) -> Repository:
        self.github_repo_name = repo
        self.github_repo = self.github_handle.get_user().get_repo(repo)

        return self.github_repo
    
    def getRepositoryContents(self) -> list:
        result = []
        contents = self.github_repo.get_contents("")
        while contents:
            file_content = contents.pop(0)
            if file_content.type == "dir":
                contents.extend(self.github_repo.get_contents(file_content.path))
            else:
                if file_content.name.endswith(self.extensions):
                    result.append(file_content)

        return result
    
    def getRepositoryContent(self, file_path: str) -> ContentFile:
        return self.github_repo.get_contents(file_path)
    
    def getName(self) -> str:
        return self.github_repo_name
    
    def getTopics(self) -> str:
        return self.github_repo.get_topics()
    
    def getStars(self) -> str:
        return self.github_repo.stargazers_count
    
    def setExtensions(self, extensions = ".md, .py"):
        self.extensions = tuple(extensions.replace(" ", "").split(","))
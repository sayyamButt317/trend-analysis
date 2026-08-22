
class LinkedInScraperException(Exception):
    pass


class AuthenticationError(LinkedInScraperException):
    pass


class RateLimitError(LinkedInScraperException):
    def __init__(self, message: str, suggested_wait_time: int = 300):
        super().__init__(message)
        self.suggested_wait_time = suggested_wait_time


class ElementNotFoundError(LinkedInScraperException):
    pass


class ProfileNotFoundError(LinkedInScraperException):
    pass


class NetworkError(LinkedInScraperException):
    pass


class ScrapingError(LinkedInScraperException):
    pass

"""Scraper configuration"""
from dataclasses import dataclass


@dataclass
class WBConfig:
    """Configuration for Wildberries scraper"""
    phone: str
    headless: bool = True
    slow_mo: int = 100
    state_file_path: str = "storage/state.json"
    downloads_path: str = "storage/downloads"

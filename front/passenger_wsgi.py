import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from app import crear_app

application = crear_app()

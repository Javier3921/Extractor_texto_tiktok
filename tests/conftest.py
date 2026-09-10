"""Configuracion compartida de pytest."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.models import Segment  # noqa: E402


@pytest.fixture
def english_segments():
    return [
        Segment(0.0, 3.0, "Today we are going to build a REST API using Node.js and Express."),
        Segment(3.0, 6.5, "Then we deploy it with Docker and Kubernetes on AWS."),
        Segment(6.5, 9.0, "We use PostgreSQL as the database and OAuth 2.0 for auth."),
    ]


@pytest.fixture
def spanish_segments():
    return [
        Segment(0.0, 3.0, "Hoy vamos a construir una API REST con Node.js y Express."),
        Segment(3.0, 6.0, "Luego la desplegamos con Docker."),
    ]


@pytest.fixture
def sample_report_dict():
    return {
        "title": "Construir una REST API con Node.js",
        "original_language": "English",
        "translated_to_spanish": True,
        "executive_summary": "El video explica como crear una API REST.",
        "detailed_explanation": "Se define un servidor Express y rutas CRUD.",
        "technologies": [
            {"category": "framework", "name": "Express"},
            {"category": "lenguaje", "name": "JavaScript"},
        ],
        "technical_concepts": ["REST", "CRUD", "Middleware"],
        "architecture": "Cliente -> API Express -> PostgreSQL.",
        "code_analysis": "Se muestra un archivo index.js con app.get y app.post.",
        "best_practices": ["Uso de variables de entorno"],
        "risks": ["No se valida la entrada del usuario"],
        "recommendations": ["Anadir validacion con Joi o Zod"],
        "difficulty": "Intermedio",
        "applications": ["Backends de aplicaciones web"],
        "conclusion": "Buen punto de partida para APIs con Node.js.",
    }

"""
Constantes comerciales y de cobertura para Ferretería El Constructor.
Exclusividad operativa en los 10 municipios del Valle de Aburrá, Antioquia, Colombia.
"""

VALLE_DE_ABURRA_MUNICIPALITIES = [
    "Medellín",
    "Bello",
    "Itagüí",
    "Envigado",
    "Sabaneta",
    "Copacabana",
    "La Estrella",
    "Girardota",
    "Caldas",
    "Barbosa"
]

MUNICIPALITY_CHOICES = [(m, m) for m in VALLE_DE_ABURRA_MUNICIPALITIES]

DEFAULT_DEPARTMENT = "Antioquia"

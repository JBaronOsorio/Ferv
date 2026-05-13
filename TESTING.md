"""
TESTING GUIDE - Proyecto Ferv
==============================

Esta guía describe cómo ejecutar y mantener la suite de pruebas automáticas del proyecto Ferv.

## Estructura de Pruebas

```
ferv_project/
├── pytest.ini                          # Configuración de pytest
├── conftest.py                         # Fixtures compartidas globales
├── user/
│   └── tests/
│       ├── __init__.py
│       ├── test_registration.py        # HU06: Registro
│       ├── test_profile.py             # HU05: Perfil de usuario
│       └── test_authentication.py      # HU07: Rutas protegidas
├── graph/
│   └── tests/
│       ├── __init__.py
│       ├── test_graph.py               # HU01, HU09: Agregar/eliminar nodos
│       └── test_views.py               # HU07: Acceso al mapa
└── recommendation/
    └── tests/
        ├── __init__.py
        └── test_recommendation.py      # HU02: Chat de recomendación
```

## Historias de Usuario Cubiertas

### HU05: Guardar Perfil
- ✅ Guardar perfil exitosamente con todas las preferencias
- ✅ Guardar perfil sin seleccionar preferencias
- ✅ Editar perfil existente

### HU06: Registro
- ✅ Registro exitoso con email y contraseña válidos
- ✅ Rechazar email duplicado
- ✅ Validar que las contraseñas coincidan

### HU07: Rutas Protegidas
- ✅ Acceso autenticado al mapa
- ✅ Acceso autenticado a welcome
- ✅ Acceso autenticado a perfil
- ✅ Redirigir usuarios no autenticados a login
- ✅ Login exitoso
- ✅ Logout exitoso

### HU01: Agregar Nodo al Grafo
- ✅ Agregar nodo exitosamente
- ✅ Rechazar nodo duplicado (restricción unique)
- ✅ Validar JSON válido
- ✅ Validar que node_id es requerido

### HU02: Chat de Recomendación ⏸️
- ⏸️ Recomendación exitosa (mock Gemini) — SKIPPED
- ⏸️ Manejo de errores de Gemini — SKIPPED
- ⏸️ One-shot recommendation — SKIPPED

### HU09: Eliminar Nodo ⏸️
- ⏸️ Eliminar nodo exitosamente — SKIPPED
- ⏸️ Error al eliminar nodo inexistente — SKIPPED
- ⏸️ Validar permisos (no puedes borrar nodo de otro usuario) — SKIPPED

## Instalación de Dependencias

```bash
# Instalar pytest y extensiones de Django
pip install pytest pytest-django pytest-cov

# Instalar todas las dependencias del proyecto
pip install -r requirements.txt
```

## Ejecutar las Pruebas

### Ejecutar todas las pruebas
```bash
pytest
```

### Ejecutar pruebas de una app específica
```bash
pytest ferv_project/user/tests/
pytest ferv_project/graph/tests/
pytest ferv_project/recommendation/tests/
```

### Ejecutar un archivo de pruebas específico
```bash
pytest ferv_project/user/tests/test_registration.py
pytest ferv_project/user/tests/test_profile.py
pytest ferv_project/user/tests/test_authentication.py
```

### Ejecutar una prueba específica
```bash
pytest ferv_project/user/tests/test_registration.py::TestUserRegistration::test_registration_successful
```

### Ejecutar solo las pruebas que NO están marcadas como skip
```bash
pytest -m "not skip"
```

### Ver pruebas skipped
```bash
pytest -v --collect-only | grep SKIPPED
```

### Ejecutar con cobertura
```bash
pytest --cov=ferv_project --cov-report=html
# Abre htmlcov/index.html en el navegador
```

### Ejecutar solo pruebas rápidas (sin slow)
```bash
pytest -m "not slow"
```

### Modo verbose (más detalles)
```bash
pytest -v
```

### Mostrar prints durante las pruebas
```bash
pytest -s
```

## Estructura de las Pruebas

Cada test sigue este patrón:

```python
def test_feature_scenario(fixtures):
    """
    HU## — [Happy Path|Alternative]: Descripción concisa.
    
    Given: Condiciones iniciales
    When: Acción que se realiza
    Then: Resultado esperado
    """
    # Arrange
    setup_data()
    
    # Act
    response = client.post(url, data)
    
    # Assert
    assert response.status_code == 200
```

## Fixtures Disponibles

Las fixtures están definidas en `ferv_project/conftest.py`:

### Datos de Usuario
- `user_data`: Dict con credenciales de prueba
- `test_user`: Usuario sin perfil completado
- `test_user_with_profile`: Usuario con perfil completado
- `client`: Django test client
- `authenticated_client`: Client con usuario autenticado

### Datos de Lugar
- `test_place`: Lugar de prueba principal
- `test_place_2`: Segundo lugar de prueba

### Datos de Grafo
- `test_graph_node`: Nodo del grafo
- `test_graph_edge`: Edge del grafo

### Datos de Perfil
- `complete_profile_data`: Datos completos de perfil
- `minimal_profile_data`: Datos mínimos (vacío)

## Endpoints Testeados

### User App
- POST /user/register/ — Registro de usuarios
- GET/POST /user/profile-setup/ — Configuración inicial de perfil
- GET/POST /user/profile/edit/ — Edición de perfil
- GET /user/profile/ — Ver perfil
- POST /user/ — Login
- POST /user/logout/ — Logout

### Graph App
- GET /graph/ — Index (público)
- GET /graph/map/ — Mapa (protegido)
- GET /graph/welcome/ — Bienvenida (protegido)
- POST /graph/add-node/ — Agregar nodo (protegido)
- GET /graph/api/fetch-graph/ — Obtener grafo (protegido)

### Recommendation App
- POST /api/recommendation/recommend/ — Chat de recomendación (pendiente)

## Mocking

Para las pruebas de HU02 (chat), se usa `unittest.mock`:

```python
from unittest.mock import patch, MagicMock

@patch('recommendation.llm_client.GeminiClient.generate_recommendations')
def test_with_mock(mock_gemini, client, test_user_with_profile):
    mock_gemini.return_value = {'recommendations': [...]}
    response = client.post(url, data)
```

## Marcadores (Markers)

Los tests pueden estar marcados con:
- `@pytest.mark.skip` — Prueba pendiente (endpoint no implementado)
- `@pytest.mark.django_db` — Prueba que necesita acceso a BD
- `@pytest.mark.integration` — Prueba de integración
- `@pytest.mark.slow` — Prueba lenta

## Base de Datos de Prueba

Django crea automáticamente una BD de prueba temporal. No es necesario hacer nada especial.

La configuración está en `pytest.ini`:
```ini
DJANGO_SETTINGS_MODULE = ferv_project.settings
```

## Troubleshooting

### Error: "django.core.exceptions.ImproperlyConfigured"
Verifica que `pytest.ini` existe en la raíz del proyecto.

### Error: "No module named 'ferv_project'"
Asegúrate de estar en el directorio correcto:
```bash
cd c:/Users/USUARIO/Desktop/INGENIERA/7_SeptimoSemestre/Proyecto2/Ferv
```

### Las pruebas no encuentran las fixtures
Verifica que `conftest.py` está en `ferv_project/` (no en `ferv_project/ferv_project/`).

### Error de timeout en pruebas
Usa `--timeout=300` para aumentar el timeout:
```bash
pytest --timeout=300
```

## Próximas Tareas

Para completar la cobertura de pruebas:

1. **HU02**: Implementar endpoint de chat de recomendación
   - Crear view en `recommendation/views.py`
   - Remover @skip de tests en `test_recommendation.py`

2. **HU09**: Implementar eliminación de nodos
   - Crear endpoint DELETE /graph/delete-node/<node_id>
   - Remover @skip de tests en `test_graph.py`

3. **HU10**: Implementar filtros del mapa (cuando se especifique)
   - Agregar nuevos tests

## Referencia Rápida

```bash
# Correr todo
pytest

# Correr con cobertura
pytest --cov

# Correr especificado
pytest ferv_project/user/tests/test_registration.py::TestUserRegistration::test_registration_successful

# Ver skipped
pytest --collect-only | grep SKIPPED

# Modo verbose + prints
pytest -v -s

# Solo tests no-skip
pytest -m "not skip"
```

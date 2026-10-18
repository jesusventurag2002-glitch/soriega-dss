import os
import sys
import tempfile
from datetime import date, timedelta
from urllib.parse import quote

import pytest

# La base de pruebas es un SQLite temporal: nunca toca la base PostgreSQL real.
_db = os.path.join(tempfile.mkdtemp(), 'pruebas.db')
os.environ['DATABASE_URL'] = f'sqlite:///{_db}'
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as aplicacion  # noqa: E402


def cabeceras(nombre='María González', rol='analista'):
    return {'X-Usuario': quote(nombre), 'X-Rol': rol}


ANALISTA = cabeceras()
GERENTE = cabeceras('Carlos Ramírez', 'gerente')


@pytest.fixture
def app():
    with aplicacion.app.app_context():
        aplicacion.db.drop_all()
        aplicacion.db.create_all()
        yield aplicacion
        aplicacion.db.session.remove()


@pytest.fixture
def cliente(app):
    return app.app.test_client()


@pytest.fixture
def datos_basicos(app):
    """Un artículo con 100 u en el almacén, 2 u en Barcelona y 20 u vendidas en 10 días (2/día).

    Con 15 días de horizonte la necesidad es 2 * 15 - 2 = 28 unidades.
    """
    db = app.db
    db.session.add(app.Articulo(codigo='A1', nombre='Aceite 1L', nombredegrupo='VIVERES', costoex=5))
    db.session.add(app.Inventario(articulo_codigo='A1', origen_inventario='INVAL', existencia=100))
    db.session.add(app.Inventario(articulo_codigo='A1', origen_inventario='INV', sucursal='Barcelona', existencia=2))
    inicio = date(2026, 10, 1)
    for dia in (0, 9):
        db.session.add(app.Venta(documento='F', articulo_codigo='A1', cantidad_neta=10, precio_fin_moneda_local=1,
                                 factor_sistema=1, factura_real_usd=1, fecha_emision=inicio + timedelta(days=dia),
                                 sucursal='Barcelona'))
    db.session.commit()
    return app

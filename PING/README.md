# PING — Tu zona, en conexión

Primera actualización de recuperación del proyecto PING. Conserva Flask, las plantillas HTML, el feed local, Leaflet/OpenStreetMap, publicaciones por categoría, grupos, perfiles y selección de zona; renueva la interfaz y corrige rutas y validaciones.

## Requisitos

- Python 3.10 o posterior
- pip
- Internet para cargar Leaflet, los mapas de OpenStreetMap y la fuente web

## Ejecutar en local (sin Turso)

```bash
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
# En Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
python app.py
```

Abre `http://127.0.0.1:5000`. Sin las variables de Turso, PING crea una base SQLite local en `instance/ping.db`.

## Usar Turso (despliegue)

Configura estas variables de entorno en el servicio de despliegue:

- `TURSO_DATABASE_URL`: URL de la base de datos Turso.
- `TURSO_AUTH_TOKEN`: token de acceso de esa base de datos.
- `SECRET_KEY`: una clave aleatoria larga para la aplicación.

Cuando están configuradas las dos variables de Turso, la aplicación utiliza Turso; si no, usa SQLite local. No guardes tokens en el repositorio ni compartas capturas que los muestren.

Para comprobar la conexión, abre `/api/health`: debería devolver `status: ok` y el tipo de base de datos utilizado.

## Cuentas: registro e inicio de sesión

- Registro con nombre visible, correo y contraseña (mínimo 8 caracteres).
- Inicio y cierre de sesión con cookie de sesión de Flask.
- Las contraseñas se guardan mediante hash seguro de Werkzeug, nunca en texto plano.
- Los nombres de usuario y correos deben ser únicos.
- Puedes explorar el feed y el mapa como invitado; para publicar, crear grupos o unirte a ellos, debes iniciar sesión.
- Las cuentas se guardan en la tabla `users` de la misma base SQLite/Turso que usa PING.

Para despliegue HTTPS, configura `SECRET_KEY` con una clave aleatoria robusta y `PING_HTTPS=1`. No reutilices una clave publicada.

## Funciones incluidas

- Feed de avisos y búsqueda por texto/categoría.
- Publicación de avisos con categoría y ubicación aproximada.
- Mapa interactivo con marcadores de publicaciones.
- Selección manual de zona y opción de solicitar geolocalización.
- Creación de grupos y unión a grupos.
- Perfil básico y cambio de nombre visible (requiere sesión).
- Validación de longitud, categorías y coordenadas; consultas SQL parametrizadas.

## Importante antes de publicar

La autenticación básica ya está implementada, pero antes de abrir la aplicación al público conviene añadir verificación de correo, recuperación de contraseña, límites de frecuencia, moderación/reportes, protección CSRF adecuada al despliegue y una política de privacidad. La geolocalización del navegador requiere permiso y un contexto seguro (HTTPS) fuera de `localhost`.

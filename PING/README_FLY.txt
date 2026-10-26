PING 2.1 — archivos de despliegue Fly.io

Esta carpeta contiene Dockerfile y fly.toml para el despliegue.
En GitHub, asegúrate de que los archivos están dentro de PING/.
En Fly.io: Working directory = PING; Config path = PING/fly.toml.

IMPORTANTE: en fly.toml cambia el nombre app = "ping-prod-change-this-if-unavailable"
por el nombre real/único de la app de Fly.io que hayas elegido. Si ya creaste una app
con otro nombre, deben coincidir exactamente.

Variables/secretos requeridos en Fly.io:
TURSO_DATABASE_URL = URL de la base de datos Turso
TURSO_AUTH_TOKEN = token secreto de Turso
SECRET_KEY = una cadena aleatoria larga, privada y estable

No subas el token ni SECRET_KEY a GitHub. La app usa Turso solo si las dos variables
TURSO_DATABASE_URL y TURSO_AUTH_TOKEN están presentes. Después de desplegar, comprueba
https://TU-APP.fly.dev/api/health; debe indicar status=ok y database=turso.

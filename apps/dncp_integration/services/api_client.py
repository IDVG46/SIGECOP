import requests
from datetime import datetime, timedelta
import environ

env = environ.Env()


class DNCPApiClient:
    BASE_URL = "https://www.contrataciones.gov.py/datos/api/v3/doc"
    TOKEN_URL = f"{BASE_URL}/oauth/token"

    def __init__(self, timeout=30):
        self.timeout = timeout
        self.access_token = None
        self.token_expiry = None
        self.request_token = env("DNCP_REQUEST_TOKEN", default=None)

    def _get_access_token(self):
        """Obtiene un nuevo access_token usando el request_token."""
        payload = {"request_token": self.request_token}
        response = requests.post(self.TOKEN_URL, json=payload, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()
        self.access_token = data["access_token"]
        # Token válido 15 minutos, renovar 1 minuto antes
        self.token_expiry = datetime.now() + timedelta(minutes=14)
        return self.access_token

    def _ensure_token(self):
        """Asegura que el token esté válido, renueva si es necesario."""
        if self.request_token is None:
            return None  # Sin autenticación
        
        if self.access_token is None or datetime.now() >= self.token_expiry:
            self._get_access_token()
        return self.access_token

    def _get_headers(self):
        """Genera headers con token si está disponible."""
        headers = {"Content-Type": "application/json"}
        token = self._ensure_token()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def search_processes(self, params):
        """Busca procesos de licitación."""
        url = f"{self.BASE_URL}/search/processes"
        headers = self._get_headers()
        response = requests.get(url, params=params, headers=headers, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def get_record(self, ocid):
        """Obtiene detalles de un proceso por OCID."""
        url = f"{self.BASE_URL}/ocds/record/{ocid}"
        headers = self._get_headers()
        response = requests.get(url, headers=headers, timeout=self.timeout)
        response.raise_for_status()
        return response.json()
    
    def _ensure_token(self):
        """Asegura que el token esté válido, renueva si es necesario."""
        if self.request_token is None:
            print("[!] Sin token DNCP - modo limitado (15 req/min)")
            return None
        
        if self.access_token is None or datetime.now() >= self.token_expiry:
            print("[*] Renovando token DNCP...")
            self._get_access_token()
            print(f"[OK] Token obtenido: {self.access_token[:20]}...")
        return self.access_token
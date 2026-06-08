"""
Outil de lecture du contenu des articles

Convertit une URL en Markdown adapté aux LLM via l'API Jina AI Reader.
Prend en charge la lecture unitaire et par lot, avec limitation de débit et contrôle de concurrence intégrés.

"""

import time
from typing import Dict, List

import requests

from ..utils.errors import MCPError, InvalidParameterError


# Configuration de Jina Reader
JINA_READER_BASE = "https://r.jina.ai"
DEFAULT_TIMEOUT = 30  # secondes
MAX_BATCH_SIZE = 5  # nombre maximal d'articles par lot
BATCH_INTERVAL = 5.0  # intervalle entre les requêtes par lot (secondes)


class ArticleReaderTools:
    """Classe des outils de lecture du contenu des articles"""

    def __init__(self, project_root: str = None, jina_api_key: str = None):
        """
        Initialise l'outil de lecture des articles

        Args:
            project_root: répertoire racine du projet
            jina_api_key: clé API Jina (facultatif, une clé permet d'augmenter la limite de débit)
        """
        self.project_root = project_root
        self.jina_api_key = jina_api_key
        self._last_request_time = 0.0

    def _build_headers(self) -> Dict[str, str]:
        """Construit les en-têtes de la requête"""
        headers = {
            "Accept": "text/markdown",
            "X-Return-Format": "markdown",
            "X-No-Cache": "true",
        }
        if self.jina_api_key:
            headers["Authorization"] = f"Bearer {self.jina_api_key}"
        return headers

    def _throttle(self):
        """Contrôle de débit : garantit un intervalle de 5 secondes entre les requêtes"""
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < BATCH_INTERVAL:
            time.sleep(BATCH_INTERVAL - elapsed)
        self._last_request_time = time.time()

    def read_article(
        self,
        url: str,
        timeout: int = DEFAULT_TIMEOUT
    ) -> Dict:
        """
        Lit le contenu d'un seul article (format Markdown)

        Args:
            url: lien de l'article
            timeout: délai d'expiration de la requête (secondes), 30 par défaut

        Returns:
            dictionnaire du contenu de l'article
        """
        try:
            if not url or not url.startswith(("http://", "https://")):
                raise InvalidParameterError(
                    f"URL invalide : {url}",
                    suggestion="L'URL doit commencer par http:// ou https://"
                )

            self._throttle()

            response = requests.get(
                f"{JINA_READER_BASE}/{url}",
                headers=self._build_headers(),
                timeout=timeout
            )

            if response.status_code == 200:
                return {
                    "success": True,
                    "data": {
                        "url": url,
                        "content": response.text,
                        "format": "markdown",
                        "content_length": len(response.text)
                    }
                }
            elif response.status_code == 429:
                return {
                    "success": False,
                    "error": {
                        "code": "RATE_LIMITED",
                        "message": "Limite de débit de Jina Reader atteinte, veuillez réessayer plus tard",
                        "suggestion": "Limite gratuite : 100 RPM / 2 requêtes simultanées, une clé API permet d'augmenter le quota"
                    }
                }
            else:
                return {
                    "success": False,
                    "error": {
                        "code": "FETCH_FAILED",
                        "message": f"HTTP {response.status_code}: {response.reason}",
                        "url": url
                    }
                }

        except requests.Timeout:
            return {
                "success": False,
                "error": {
                    "code": "TIMEOUT",
                    "message": f"Délai de requête dépassé ({timeout} secondes)",
                    "url": url,
                    "suggestion": "Vous pouvez essayer d'augmenter le paramètre timeout"
                }
            }
        except MCPError as e:
            return {"success": False, "error": e.to_dict()}
        except Exception as e:
            return {
                "success": False,
                "error": {
                    "code": "REQUEST_ERROR",
                    "message": str(e),
                    "url": url
                }
            }

    def read_articles_batch(
        self,
        urls: List[str],
        timeout: int = DEFAULT_TIMEOUT
    ) -> Dict:
        """
        Lit le contenu de plusieurs articles par lot (5 maximum, intervalle de 5 secondes)

        Args:
            urls: liste des liens d'articles
            timeout: délai d'expiration de la requête pour chaque article (secondes)

        Returns:
            résultat de la lecture par lot
        """
        try:
            if not urls:
                raise InvalidParameterError(
                    "La liste d'URL ne peut pas être vide",
                    suggestion="Veuillez fournir au moins une URL"
                )

            # Limite à 5 articles maximum
            actual_urls = urls[:MAX_BATCH_SIZE]
            skipped = len(urls) - len(actual_urls)

            results = []
            succeeded = 0
            failed = 0

            for i, url in enumerate(actual_urls):
                result = self.read_article(url=url, timeout=timeout)

                results.append({
                    "index": i + 1,
                    "url": url,
                    "success": result["success"],
                    "data": result.get("data"),
                    "error": result.get("error")
                })

                if result["success"]:
                    succeeded += 1
                else:
                    failed += 1

            return {
                "success": True,
                "summary": {
                    "description": "Résultat de la lecture d'articles par lot",
                    "requested": len(urls),
                    "processed": len(actual_urls),
                    "succeeded": succeeded,
                    "failed": failed,
                    "skipped": skipped,
                    "interval_seconds": BATCH_INTERVAL,
                },
                "articles": results,
                "note": f"{skipped} article(s) ignoré(s) (limite de {MAX_BATCH_SIZE} par lot)" if skipped > 0 else None
            }

        except MCPError as e:
            return {"success": False, "error": e.to_dict()}
        except Exception as e:
            return {
                "success": False,
                "error": {
                    "code": "BATCH_ERROR",
                    "message": str(e)
                }
            }

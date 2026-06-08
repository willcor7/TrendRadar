# coding=utf-8
"""
Module de récupération de données

Responsable de la collecte des actualités depuis l'API NewsNow. Prend en charge :
- la récupération des données d'une seule plateforme
- la collecte des données de plusieurs plateformes en masse
- un mécanisme de réessai automatique
- la prise en charge d'un proxy
"""

import json
import random
import time
from typing import Dict, List, Tuple, Optional, Union
from urllib.parse import urlparse

import requests


class DataFetcher:
    """Récupérateur de données"""

    # Adresse de l'API par défaut (projet newsnow : https://github.com/ourongxing/newsnow)
    DEFAULT_API_URL = "https://newsnow.busiyi.world/api/s"

    # En-têtes de requête par défaut
    DEFAULT_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Connection": "keep-alive",
        "Cache-Control": "no-cache",
    }

    def __init__(
        self,
        proxy_url: Optional[str] = None,
        api_url: Optional[str] = None,
    ):
        """
        Initialise le récupérateur de données

        Args:
            proxy_url: URL du serveur proxy (optionnel)
            api_url: URL de base de l'API (optionnel ; par défaut, utilise DEFAULT_API_URL)
        """
        self.proxy_url = proxy_url
        self.api_url = api_url or self.DEFAULT_API_URL

    @staticmethod
    def _check_domain_safety(
        items: List[Dict],
        expected_domain: str,
    ) -> Optional[str]:
        """
        Vérifie que les liens présents dans les données retournées sont en HTTPS et que leur
        domaine correspond à celui attendu (les sous-domaines sont autorisés).

        Vérifie à la fois les champs url et mobileUrl, en analysant le nom d'hôte avec la
        bibliothèque standard afin d'éviter qu'un userinfo (comme https://baidu.com@evil.com)
        ne contourne la vérification.

        Args:
            items: liste des éléments de données retournés par l'API
            expected_domain: domaine attendu (comme "baidu.com")

        Returns:
            None si tout est sûr, sinon la description de la première anomalie rencontrée
        """
        expected = expected_domain.lower().strip()
        if not expected:
            return None

        for item in items:
            for field in ("url", "mobileUrl"):
                url = item.get(field, "")
                if not url:
                    continue
                parsed = urlparse(url)
                if parsed.scheme != "https":
                    return f"{url} (non HTTPS ou format invalide)"
                hostname = (parsed.hostname or "").lower()
                if hostname != expected and not hostname.endswith("." + expected):
                    return f"{hostname} (provient de {url})"
        return None

    def fetch_data(
        self,
        id_info: Union[str, Tuple[str, str]],
        max_retries: int = 2,
        min_retry_wait: int = 3,
        max_retry_wait: int = 5,
    ) -> Tuple[Optional[str], str, str]:
        """
        Récupère les données de l'ID indiqué, avec prise en charge du réessai

        Args:
            id_info: ID de plateforme, ou tuple (ID de plateforme, alias)
            max_retries: nombre maximal de réessais
            min_retry_wait: délai d'attente minimal avant un réessai (secondes)
            max_retry_wait: délai d'attente maximal avant un réessai (secondes)

        Returns:
            tuple (texte de la réponse, ID de plateforme, alias) ; en cas d'échec, le texte de la réponse vaut None
        """
        if isinstance(id_info, tuple):
            id_value, alias = id_info
        else:
            id_value = id_info
            alias = id_value

        url = f"{self.api_url}?id={id_value}&latest"

        proxies = None
        if self.proxy_url:
            proxies = {"http": self.proxy_url, "https": self.proxy_url}

        retries = 0
        while retries <= max_retries:
            try:
                response = requests.get(
                    url,
                    proxies=proxies,
                    headers=self.DEFAULT_HEADERS,
                    timeout=10,
                )
                response.raise_for_status()

                data_text = response.text
                data_json = json.loads(data_text)

                status = data_json.get("status", "inconnu")
                if status not in ["success", "cache"]:
                    raise ValueError(f"État de réponse anormal : {status}")

                status_info = "données les plus récentes" if status == "success" else "données en cache"
                print(f"Récupération de {id_value} réussie ({status_info})")
                return data_text, id_value, alias

            except Exception as e:
                retries += 1
                if retries <= max_retries:
                    base_wait = random.uniform(min_retry_wait, max_retry_wait)
                    additional_wait = (retries - 1) * random.uniform(1, 2)
                    wait_time = base_wait + additional_wait
                    print(f"Échec de la requête {id_value} : {e}. Nouvel essai dans {wait_time:.2f} secondes...")
                    time.sleep(wait_time)
                else:
                    print(f"Échec de la requête {id_value} : {e}")
                    return None, id_value, alias

        return None, id_value, alias

    def crawl_websites(
        self,
        ids_list: List[Union[str, Tuple[str, str]]],
        request_interval: int = 100,
        domain_rules: Optional[Dict[str, str]] = None,
    ) -> Tuple[Dict, Dict, List]:
        """
        Collecte les données de plusieurs sites web

        Args:
            ids_list: liste des ID de plateformes ; chaque élément peut être une chaîne ou un tuple (ID de plateforme, alias)
            request_interval: intervalle entre les requêtes (millisecondes)
            domain_rules: règles de vérification de sécurité des domaines, au format {ID de plateforme: domaine attendu} (optionnel)

        Returns:
            tuple (dictionnaire des résultats, correspondance ID vers nom, liste des ID en échec)
        """
        results = {}
        id_to_name = {}
        failed_ids = []
        domain_rules = domain_rules or {}

        for i, id_info in enumerate(ids_list):
            if isinstance(id_info, tuple):
                id_value, name = id_info
            else:
                id_value = id_info
                name = id_value

            id_to_name[id_value] = name
            response, _, _ = self.fetch_data(id_info)

            if response:
                try:
                    data = json.loads(response)
                    items = data.get("items", [])

                    # Vérification de la sécurité du domaine
                    expected_domain = domain_rules.get(id_value, "")
                    if expected_domain:
                        bad_reason = self._check_domain_safety(items, expected_domain)
                        if bad_reason:
                            print(f"⚠️ Alerte de sécurité : les données retournées par {name}({id_value}) n'ont pas passé la vérification de sécurité du domaine !")
                            print(f"   Domaine attendu : https://*.{expected_domain}")
                            print(f"   Source de l'anomalie : {bad_reason}")
                            print(f"   Adresse de l'API actuelle : {self.api_url}")
                            print(f"   Les données de cette plateforme ont été ignorées ; veuillez vérifier si la source de l'API est fiable")
                            failed_ids.append(id_value)
                            continue

                    results[id_value] = {}

                    for index, item in enumerate(items, 1):
                        title = item.get("title")
                        # Ignore les titres invalides (None, float, chaîne vide)
                        if title is None or isinstance(title, float) or not str(title).strip():
                            continue
                        title = str(title).strip()
                        url = item.get("url", "")
                        mobile_url = item.get("mobileUrl", "")

                        if title in results[id_value]:
                            results[id_value][title]["ranks"].append(index)
                        else:
                            results[id_value][title] = {
                                "ranks": [index],
                                "url": url,
                                "mobileUrl": mobile_url,
                            }
                except json.JSONDecodeError:
                    print(f"Échec de l'analyse de la réponse de {id_value}")
                    failed_ids.append(id_value)
                except Exception as e:
                    print(f"Erreur lors du traitement des données de {id_value} : {e}")
                    failed_ids.append(id_value)
            else:
                failed_ids.append(id_value)

            # Intervalle entre les requêtes (sauf pour la dernière)
            if i < len(ids_list) - 1:
                actual_interval = request_interval + random.randint(-10, 20)
                actual_interval = max(50, actual_interval)
                time.sleep(actual_interval / 1000)

        print(f"Réussites : {list(results.keys())}, échecs : {failed_ids}")
        return results, id_to_name, failed_ids

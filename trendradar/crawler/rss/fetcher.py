# coding=utf-8
"""
Récupérateur RSS

Responsable de la récupération des données depuis les flux RSS configurés et de leur conversion
au format standard
"""

import time
import random
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple

import requests

from .parser import RSSParser
from trendradar.storage.base import RSSItem, RSSData
from trendradar.utils.time import get_configured_time, is_within_days, DEFAULT_TIMEZONE


@dataclass
class RSSFeedConfig:
    """Configuration d'un flux RSS"""
    id: str                     # ID du flux
    name: str                   # nom affiché
    url: str                    # URL du flux RSS
    max_items: int = 0          # nombre maximal d'entrées (0 = sans limite)
    enabled: bool = True        # flux activé ou non
    max_age_days: Optional[int] = None  # âge maximal des articles (jours), prioritaire sur le réglage global ; None = utilise le global, 0 = désactive le filtrage


class RSSFetcher:
    """Récupérateur RSS"""

    def __init__(
        self,
        feeds: List[RSSFeedConfig],
        request_interval: int = 2000,
        timeout: int = 15,
        use_proxy: bool = False,
        proxy_url: str = "",
        timezone: str = DEFAULT_TIMEZONE,
        freshness_enabled: bool = True,
        default_max_age_days: int = 3,
    ):
        """
        Initialise le récupérateur

        Args:
            feeds: liste des configurations de flux RSS
            request_interval: intervalle entre les requêtes (millisecondes)
            timeout: délai d'expiration des requêtes (secondes)
            use_proxy: utiliser un proxy ou non
            proxy_url: URL du proxy
            timezone: fuseau horaire configuré (comme 'Asia/Shanghai')
            freshness_enabled: activer ou non le filtrage par fraîcheur
            default_max_age_days: âge maximal des articles par défaut (jours)
        """
        self.feeds = [f for f in feeds if f.enabled]
        self.request_interval = request_interval
        self.timeout = timeout
        self.use_proxy = use_proxy
        self.proxy_url = proxy_url
        self.timezone = timezone
        self.freshness_enabled = freshness_enabled
        self.default_max_age_days = default_max_age_days

        self.parser = RSSParser()
        self.session = self._create_session()

    def _create_session(self) -> requests.Session:
        """Crée une session de requête"""
        session = requests.Session()
        session.headers.update({
            "User-Agent": "TrendRadar/2.0 RSS Reader (https://github.com/trendradar)",
            "Accept": "application/feed+json, application/json, application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        })

        if self.use_proxy and self.proxy_url:
            session.proxies = {
                "http": self.proxy_url,
                "https": self.proxy_url,
            }

        return session

    def _filter_by_freshness(
        self,
        items: List[RSSItem],
        feed: RSSFeedConfig,
    ) -> Tuple[List[RSSItem], int]:
        """
        Filtre les articles selon leur fraîcheur

        Args:
            items: liste des articles à filtrer
            feed: configuration du flux RSS

        Returns:
            (liste des articles après filtrage, nombre d'articles filtrés)
        """
        # Si le filtrage est désactivé globalement, retourne directement
        if not self.freshness_enabled:
            return items, 0

        # Détermine le max_age_days de ce flux
        max_days = feed.max_age_days
        if max_days is None:
            max_days = self.default_max_age_days

        # Si la valeur est 0, désactive le filtrage pour ce flux
        if max_days == 0:
            return items, 0

        # Logique de filtrage : les articles sans date de publication sont conservés
        filtered = []
        for item in items:
            if not item.published_at:
                # Pas de date de publication, on conserve
                filtered.append(item)
            elif is_within_days(item.published_at, max_days, self.timezone):
                # Dans le nombre de jours indiqué, on conserve
                filtered.append(item)
            # Sinon, on filtre

        filtered_count = len(items) - len(filtered)
        return filtered, filtered_count

    def fetch_feed(self, feed: RSSFeedConfig) -> Tuple[List[RSSItem], Optional[str]]:
        """
        Récupère un seul flux RSS

        Args:
            feed: configuration du flux RSS

        Returns:
            tuple (liste des entrées, message d'erreur)
        """
        try:
            response = self.session.get(feed.url, timeout=self.timeout)
            response.raise_for_status()

            parsed_items = self.parser.parse(response.text, feed.url)

            # Limite le nombre d'entrées (0 = sans limite)
            if feed.max_items > 0:
                parsed_items = parsed_items[:feed.max_items]

            # Conversion en RSSItem (en utilisant le fuseau horaire configuré)
            now = get_configured_time(self.timezone)
            crawl_time = now.strftime("%H:%M")
            items = []

            for parsed in parsed_items:
                item = RSSItem(
                    title=parsed.title,
                    feed_id=feed.id,
                    feed_name=feed.name,
                    url=parsed.url,
                    guid=parsed.guid or "",
                    published_at=parsed.published_at or "",
                    summary=parsed.summary or "",
                    author=parsed.author or "",
                    crawl_time=crawl_time,
                    first_time=crawl_time,
                    last_time=crawl_time,
                    count=1,
                )
                items.append(item)

            # Remarque : le filtrage par fraîcheur a été déplacé à l'étape d'envoi (_convert_rss_items_to_list).
            # Ainsi, tous les articles sont enregistrés en base de données, mais les anciens articles ne sont pas envoyés.
            print(f"[RSS] {feed.name} : {len(items)} entrées récupérées")
            return items, None

        except requests.Timeout:
            error = f"Délai d'expiration de la requête dépassé ({self.timeout}s)"
            print(f"[RSS] {feed.name} : {error}")
            return [], error

        except requests.RequestException as e:
            error = f"Échec de la requête : {e}"
            print(f"[RSS] {feed.name} : {error}")
            return [], error

        except ValueError as e:
            error = f"Échec de l'analyse : {e}"
            print(f"[RSS] {feed.name} : {error}")
            return [], error

        except Exception as e:
            error = f"Erreur inconnue : {e}"
            print(f"[RSS] {feed.name} : {error}")
            return [], error

    def fetch_all(self) -> RSSData:
        """
        Récupère tous les flux RSS

        Returns:
            objet RSSData
        """
        all_items: Dict[str, List[RSSItem]] = {}
        id_to_name: Dict[str, str] = {}
        failed_ids: List[str] = []

        # Utilise le fuseau horaire configuré
        now = get_configured_time(self.timezone)
        crawl_time = now.strftime("%H:%M")
        crawl_date = now.strftime("%Y-%m-%d")

        print(f"[RSS] Début de la récupération de {len(self.feeds)} flux RSS...")

        for i, feed in enumerate(self.feeds):
            # Intervalle entre les requêtes (avec une légère variation aléatoire)
            if i > 0:
                interval = self.request_interval / 1000
                jitter = random.uniform(-0.2, 0.2) * interval
                time.sleep(interval + jitter)

            items, error = self.fetch_feed(feed)

            id_to_name[feed.id] = feed.name

            if error:
                failed_ids.append(feed.id)
            else:
                all_items[feed.id] = items

        total_items = sum(len(items) for items in all_items.values())
        print(f"[RSS] Récupération terminée : {len(all_items)} flux réussis, {len(failed_ids)} en échec, {total_items} entrées au total")

        return RSSData(
            date=crawl_date,
            crawl_time=crawl_time,
            items=all_items,
            id_to_name=id_to_name,
            failed_ids=failed_ids,
        )

    @classmethod
    def from_config(cls, config: Dict) -> "RSSFetcher":
        """
        Crée un récupérateur à partir d'un dictionnaire de configuration

        Args:
            config: dictionnaire de configuration, au format suivant :
                {
                    "enabled": true,
                    "request_interval": 2000,
                    "freshness_filter": {
                        "enabled": true,
                        "max_age_days": 3
                    },
                    "feeds": [
                        {"id": "hacker-news", "name": "Hacker News", "url": "...", "max_age_days": 1}
                    ]
                }

        Returns:
            instance de RSSFetcher
        """
        # Lit la configuration du filtrage par fraîcheur
        freshness_config = config.get("freshness_filter", {})
        freshness_enabled = freshness_config.get("enabled", True)  # activé par défaut
        default_max_age_days = freshness_config.get("max_age_days", 3)  # 3 jours par défaut

        feeds = []
        for feed_config in config.get("feeds", []):
            # Lit et valide le max_age_days d'un flux individuel (optionnel)
            max_age_days_raw = feed_config.get("max_age_days")
            max_age_days = None
            if max_age_days_raw is not None:
                try:
                    max_age_days = int(max_age_days_raw)
                    if max_age_days < 0:
                        feed_id = feed_config.get("id", "unknown")
                        print(f"[Avertissement] Le max_age_days du flux RSS '{feed_id}' est négatif ; la valeur globale par défaut sera utilisée")
                        max_age_days = None
                except (ValueError, TypeError):
                    feed_id = feed_config.get("id", "unknown")
                    print(f"[Avertissement] Le max_age_days du flux RSS '{feed_id}' a un format incorrect : {max_age_days_raw}")
                    max_age_days = None

            feed = RSSFeedConfig(
                id=feed_config.get("id", ""),
                name=feed_config.get("name", ""),
                url=feed_config.get("url", ""),
                max_items=feed_config.get("max_items", 0),  # 0 = sans limite
                enabled=feed_config.get("enabled", True),
                max_age_days=max_age_days,  # None = utilise le global, 0 = désactivé, >0 = écrase
            )
            if feed.id and feed.url:
                feeds.append(feed)

        return cls(
            feeds=feeds,
            request_interval=config.get("request_interval", 2000),
            timeout=config.get("timeout", 15),
            use_proxy=config.get("use_proxy", False),
            proxy_url=config.get("proxy_url", ""),
            timezone=config.get("timezone", DEFAULT_TIMEZONE),
            freshness_enabled=freshness_enabled,
            default_max_age_days=default_max_age_days,
        )

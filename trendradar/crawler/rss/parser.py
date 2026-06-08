# coding=utf-8
"""
Analyseur RSS

Prend en charge l'analyse des formats RSS 2.0, Atom et JSON Feed 1.1
"""

import re
import html
import json
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Dict, Any
from email.utils import parsedate_to_datetime

try:
    import feedparser
    HAS_FEEDPARSER = True
except ImportError:
    HAS_FEEDPARSER = False
    feedparser = None


@dataclass
class ParsedRSSItem:
    """Entrée RSS après analyse"""
    title: str
    url: str
    published_at: Optional[str] = None
    summary: Optional[str] = None
    author: Optional[str] = None
    guid: Optional[str] = None


class RSSParser:
    """Analyseur RSS"""

    def __init__(self, max_summary_length: int = 500):
        """
        Initialise l'analyseur

        Args:
            max_summary_length: longueur maximale du résumé
        """
        if not HAS_FEEDPARSER:
            raise ImportError("L'analyse RSS nécessite l'installation de feedparser : pip install feedparser")

        self.max_summary_length = max_summary_length

    def parse(self, content: str, feed_url: str = "") -> List[ParsedRSSItem]:
        """
        Analyse un contenu RSS/Atom/JSON Feed

        Args:
            content: contenu du flux (XML ou JSON)
            feed_url: URL du flux (utilisée pour les messages d'erreur)

        Returns:
            liste des entrées après analyse
        """
        # Tente d'abord de détecter un JSON Feed
        if self._is_json_feed(content):
            return self._parse_json_feed(content, feed_url)

        # Utilise feedparser pour analyser le RSS/Atom
        feed = feedparser.parse(content)

        if feed.bozo and not feed.entries:
            raise ValueError(f"Échec de l'analyse RSS ({feed_url}) : {feed.bozo_exception}")

        items = []
        for entry in feed.entries:
            item = self._parse_entry(entry)
            if item:
                items.append(item)

        return items

    def _is_json_feed(self, content: str) -> bool:
        """
        Détecte si le contenu est au format JSON Feed

        Un JSON Feed doit contenir un champ version, dont la valeur est https://jsonfeed.org/version/1 ou 1.1
        """
        content = content.strip()
        if not content.startswith("{"):
            return False

        try:
            data = json.loads(content)
            version = data.get("version", "")
            return "jsonfeed.org" in version
        except (json.JSONDecodeError, TypeError):
            return False

    def _parse_json_feed(self, content: str, feed_url: str = "") -> List[ParsedRSSItem]:
        """
        Analyse le format JSON Feed 1.1

        Spécification JSON Feed : https://www.jsonfeed.org/version/1.1/

        Args:
            content: contenu du JSON Feed
            feed_url: URL du flux (utilisée pour les messages d'erreur)

        Returns:
            liste des entrées après analyse
        """
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(f"Échec de l'analyse du JSON Feed ({feed_url}) : {e}")

        items_data = data.get("items", [])
        if not items_data:
            return []

        items = []
        for item_data in items_data:
            item = self._parse_json_feed_item(item_data)
            if item:
                items.append(item)

        return items

    def _parse_json_feed_item(self, item_data: Dict[str, Any]) -> Optional[ParsedRSSItem]:
        """Analyse une seule entrée de JSON Feed"""
        url = item_data.get("url", "") or item_data.get("external_url", "")

        title = item_data.get("title", "")
        if not title:
            content_text = item_data.get("content_text", "")
            if content_text:
                title = content_text[:20] + ("..." if len(content_text) > 20 else "")

        title = self._clean_text(title)
        if not title and url:
            title = url
        if not title:
            return None

        # Date de publication (format ISO 8601)
        published_at = None
        date_str = item_data.get("date_published") or item_data.get("date_modified")
        if date_str:
            published_at = self._parse_iso_date(date_str)

        # Résumé : on privilégie summary, sinon on utilise content_text
        summary = item_data.get("summary", "")
        if not summary:
            content_text = item_data.get("content_text", "")
            content_html = item_data.get("content_html", "")
            summary = content_text or self._clean_text(content_html)

        if summary:
            summary = self._clean_text(summary)
            if len(summary) > self.max_summary_length:
                summary = summary[:self.max_summary_length] + "..."

        # Auteur
        author = None
        authors = item_data.get("authors", [])
        if authors:
            names = [a.get("name", "") for a in authors if isinstance(a, dict) and a.get("name")]
            if names:
                author = ", ".join(names)

        # GUID
        guid = item_data.get("id", "") or url

        return ParsedRSSItem(
            title=title,
            url=url,
            published_at=published_at,
            summary=summary or None,
            author=author,
            guid=guid,
        )

    def _parse_iso_date(self, date_str: str) -> Optional[str]:
        """Analyse une date au format ISO 8601"""
        if not date_str:
            return None

        try:
            # Traite les formats ISO 8601 courants
            # Remplace Z par +00:00
            date_str = date_str.replace("Z", "+00:00")
            dt = datetime.fromisoformat(date_str)
            return dt.isoformat()
        except (ValueError, TypeError):
            pass

        return None

    def parse_url(self, url: str, timeout: int = 10) -> List[ParsedRSSItem]:
        """
        Analyse un flux RSS à partir de son URL

        Args:
            url: URL du flux RSS
            timeout: délai d'expiration (secondes)

        Returns:
            liste des entrées après analyse
        """
        import requests

        response = requests.get(url, timeout=timeout, headers={
            "User-Agent": "TrendRadar/2.0 RSS Reader"
        })
        response.raise_for_status()

        return self.parse(response.text, url)

    def _parse_entry(self, entry: Any) -> Optional[ParsedRSSItem]:
        """Analyse une seule entrée"""
        title = self._clean_text(entry.get("title", ""))

        url = entry.get("link", "")
        if not url:
            links = entry.get("links", [])
            for link in links:
                if link.get("rel") == "alternate" or link.get("type", "").startswith("text/html"):
                    url = link.get("href", "")
                    break
            if not url and links:
                url = links[0].get("href", "")

        if not title:
            raw_summary = entry.get("summary") or entry.get("description", "")
            if not raw_summary:
                content = entry.get("content", [])
                if content and isinstance(content, list):
                    raw_summary = content[0].get("value", "")
            if raw_summary:
                title = self._clean_text(raw_summary)
                if len(title) > 20:
                    title = title[:20] + "..."
            if not title and url:
                title = url

        if not title:
            return None

        published_at = self._parse_date(entry)
        summary = self._parse_summary(entry)
        author = self._parse_author(entry)
        guid = entry.get("id") or entry.get("guid", {}).get("value") or url

        return ParsedRSSItem(
            title=title,
            url=url,
            published_at=published_at,
            summary=summary,
            author=author,
            guid=guid,
        )

    def _clean_text(self, text: str) -> str:
        """Nettoie le texte"""
        if not text:
            return ""

        # Décode les entités HTML
        text = html.unescape(text)

        # Supprime les balises HTML
        text = re.sub(r'<[^>]+>', '', text)

        # Supprime les espaces superflus
        text = re.sub(r'\s+', ' ', text)

        return text.strip()

    def _parse_date(self, entry: Any) -> Optional[str]:
        """Analyse la date de publication"""
        # feedparser analyse automatiquement la date dans published_parsed
        date_struct = entry.get("published_parsed") or entry.get("updated_parsed")

        if date_struct:
            try:
                dt = datetime(*date_struct[:6])
                return dt.isoformat()
            except (ValueError, TypeError):
                pass

        # Tente une analyse manuelle
        date_str = entry.get("published") or entry.get("updated")
        if date_str:
            try:
                dt = parsedate_to_datetime(date_str)
                return dt.isoformat()
            except (ValueError, TypeError):
                pass

            # Tente le format ISO
            try:
                dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                return dt.isoformat()
            except (ValueError, TypeError):
                pass

        return None

    def _parse_summary(self, entry: Any) -> Optional[str]:
        """Analyse le résumé"""
        summary = entry.get("summary") or entry.get("description", "")

        if not summary:
            # Tente de le récupérer depuis content
            content = entry.get("content", [])
            if content and isinstance(content, list):
                summary = content[0].get("value", "")

        if not summary:
            return None

        summary = self._clean_text(summary)

        # Tronque les résumés trop longs
        if len(summary) > self.max_summary_length:
            summary = summary[:self.max_summary_length] + "..."

        return summary

    def _parse_author(self, entry: Any) -> Optional[str]:
        """Analyse l'auteur"""
        author = entry.get("author")
        if author:
            return self._clean_text(author)

        # Tente de le récupérer depuis dc:creator
        author = entry.get("dc_creator")
        if author:
            return self._clean_text(author)

        # Tente de le récupérer depuis la liste authors
        authors = entry.get("authors", [])
        if authors:
            names = [a.get("name", "") for a in authors if a.get("name")]
            if names:
                return ", ".join(names)

        return None

# coding=utf-8
"""
Module de filtrage intelligent par IA

Classe les actualités par étiquettes à l'aide de l'IA :
1. Étape A : extraction d'étiquettes structurées à partir de la description des centres d'intérêt de l'utilisateur
2. Étape B : classification par lot des titres d'actualités selon ces étiquettes
"""

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from trendradar.ai.client import AIClient
from trendradar.ai.prompt_loader import load_prompt_template


@dataclass
class AIFilterResult:
    """Résultat du filtrage IA, transmis aux modules de rapport et de notification"""
    tags: List[Dict] = field(default_factory=list)
    # [{"tag": str, "description": str, "count": int, "items": [
    #     {"title": str, "source_id": str, "source_name": str,
    #      "url": str, "mobile_url": str, "rank": int, "ranks": [...],
    #      "first_time": str, "last_time": str, "count": int,
    #      "relevance_score": float, "source_type": str}
    # ]}]
    total_matched: int = 0       # Nombre total d'actualités correspondantes
    total_processed: int = 0     # Nombre total d'actualités traitées
    success: bool = False
    error: str = ""


class AIFilter:
    """Filtre intelligent par IA"""

    def __init__(
        self,
        ai_config: Dict[str, Any],
        filter_config: Dict[str, Any],
        get_time_func: Callable,
        debug: bool = False,
    ):
        self.client = AIClient(ai_config)
        self.filter_config = filter_config
        self.batch_size = filter_config.get("BATCH_SIZE", 200)
        self.get_time_func = get_time_func
        self.debug = debug

        # Chargement des modèles de prompts
        self.classify_system, self.classify_user = load_prompt_template(
            filter_config.get("PROMPT_FILE", "ai_filter_prompt.txt"),
            config_subdir="ai_filter", label="Filtrage IA",
        )
        self.extract_system, self.extract_user = load_prompt_template(
            filter_config.get("EXTRACT_PROMPT_FILE", "ai_filter_extract_prompt.txt"),
            config_subdir="ai_filter", label="Filtrage IA",
        )
        self.update_tags_system, self.update_tags_user = load_prompt_template(
            filter_config.get("UPDATE_TAGS_PROMPT_FILE", "update_tags_prompt.txt"),
            config_subdir="ai_filter", label="Filtrage IA",
        )

    def compute_interests_hash(self, interests_content: str, filename: str = "ai_interests.txt") -> str:
        """Calcule le hash de la description des centres d'intérêt, au format filename:md5"""
        # On retire les espaces de début et de fin ainsi que les lignes de commentaire, afin que seul un changement de contenu modifie le hash
        lines = []
        for line in interests_content.strip().splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                lines.append(line)
        normalized = "\n".join(lines)
        content_hash = hashlib.md5(normalized.encode("utf-8")).hexdigest()
        return f"{filename}:{content_hash}"

    def load_interests_content(self, interests_file: Optional[str] = None) -> Optional[str]:
        """Charge le contenu du fichier de description des centres d'intérêt

        Logique de résolution :
        - interests_file vaut None : utilisation du fichier par défaut config/ai_interests.txt
        - interests_file a une valeur : recherche uniquement dans config/custom/ai/{filename}

        Remarque : l'appelant (context.py) a déjà tranché la fusion entre config et timeline ;
        on ne relit donc pas filter_config ici, afin d'éviter tout conflit sémantique.
        """
        config_dir = Path(__file__).parent.parent.parent / "config"
        configured_file = interests_file

        if configured_file:
            # Fichier de centres d'intérêt personnalisé : recherche uniquement dans le répertoire custom/ai
            filename = configured_file
            interests_path = config_dir / "custom" / "ai" / filename
            if not interests_path.exists():
                print(f"[Filtrage IA] Fichier de description des centres d'intérêt personnalisé introuvable : {filename}")
                print(f"[Filtrage IA]   Emplacement recherché : {interests_path}")
                return None
        else:
            # Fichier de centres d'intérêt par défaut : on utilise toujours config/ai_interests.txt
            filename = "ai_interests.txt"
            interests_path = config_dir / filename
            if not interests_path.exists():
                print(f"[Filtrage IA] Fichier de description des centres d'intérêt par défaut introuvable : {filename}")
                print(f"[Filtrage IA]   Emplacement recherché : {interests_path}")
                return None

        if not interests_path.exists():
            print(f"[Filtrage IA] Fichier de description des centres d'intérêt introuvable : {interests_path}")
            return None

        content = interests_path.read_text(encoding="utf-8").strip()
        if not content:
            print("[Filtrage IA] Le fichier de description des centres d'intérêt est vide")
            return None

        return content

    def extract_tags(self, interests_content: str) -> List[Dict]:
        """
        Étape A : extraction d'étiquettes structurées à partir de la description des centres d'intérêt

        Args:
            interests_content: texte de description des centres d'intérêt de l'utilisateur

        Returns:
            [{"tag": str, "description": str}, ...]
        """
        if not self.extract_user:
            print("[Filtrage IA] Le modèle de prompt d'extraction d'étiquettes est vide")
            return []

        user_prompt = self.extract_user.replace("{interests_content}", interests_content)

        messages = []
        if self.extract_system:
            messages.append({"role": "system", "content": self.extract_system})
        messages.append({"role": "user", "content": user_prompt})

        if self.debug:
            print(f"\n[Filtrage IA][DEBUG] === Prompt d'extraction d'étiquettes ===")
            for m in messages:
                print(f"[{m['role']}]\n{m['content']}")
            print(f"[Filtrage IA][DEBUG] === Fin du prompt ===")

        try:
            response = self.client.chat(messages)

            if self.debug:
                print(f"\n[Filtrage IA][DEBUG] === Réponse brute de l'IA pour l'extraction d'étiquettes ===")
                # On met en forme le JSON pour faciliter la lecture
                self._print_formatted_json(response)
                print(f"[Filtrage IA][DEBUG] === Fin de la réponse ===")

            tags = self._parse_tags_response(response)
            print(f"[Filtrage IA] {len(tags)} étiquette(s) extraite(s)")
            for t in tags:
                print(f"   {t['tag']}: {t.get('description', '')}")

            if self.debug:
                json_str = self._extract_json(response)
                if not json_str:
                    print(f"[Filtrage IA][DEBUG] Impossible d'extraire du JSON de la réponse")
                else:
                    raw_data = json.loads(json_str)
                    raw_tags = raw_data.get("tags", [])
                    skipped = len(raw_tags) - len(tags)
                    if skipped > 0:
                        print(f"[Filtrage IA][DEBUG] {len(raw_tags)} étiquette(s) brute(s), {len(tags)} valide(s), {skipped} ignorée(s) (champ tag manquant ou format invalide)")

            return tags
        except json.JSONDecodeError as e:
            print(f"[Filtrage IA] Échec de l'extraction d'étiquettes : erreur d'analyse JSON : {e}")
            if self.debug:
                print(f"[Filtrage IA][DEBUG] Contenu JSON dont l'analyse a été tentée : {self._extract_json(response) if response else '(réponse vide)'}")
            return []
        except Exception as e:
            print(f"[Filtrage IA] Échec de l'extraction d'étiquettes : {type(e).__name__}: {e}")
            return []

    def update_tags(self, old_tags: List[Dict], interests_content: str) -> Optional[Dict]:
        """
        Étape A' : l'IA compare les anciennes étiquettes à la nouvelle description des centres d'intérêt et propose un plan de mise à jour

        Args:
            old_tags: [{"tag": str, "description": str, "id": int}, ...]
            interests_content: nouveau texte de description des centres d'intérêt

        Returns:
            {"keep": [{"tag": str, "description": str}],
             "add": [{"tag": str, "description": str}],
             "remove": [str],
             "change_ratio": float}
            Renvoie None en cas d'échec
        """
        if not self.update_tags_user:
            print("[Filtrage IA] Le modèle de prompt de mise à jour des étiquettes est vide ; repli vers une nouvelle extraction")
            return None

        # Construction du JSON des anciennes étiquettes
        old_tags_json = json.dumps(
            [{"tag": t["tag"], "description": t.get("description", "")} for t in old_tags],
            ensure_ascii=False, indent=2
        )

        user_prompt = self.update_tags_user.replace(
            "{old_tags_json}", old_tags_json
        ).replace(
            "{interests_content}", interests_content
        )

        messages = []
        if self.update_tags_system:
            messages.append({"role": "system", "content": self.update_tags_system})
        messages.append({"role": "user", "content": user_prompt})

        if self.debug:
            print(f"\n[Filtrage IA][DEBUG] === Prompt de mise à jour des étiquettes ===")
            for m in messages:
                print(f"[{m['role']}]\n{m['content']}")
            print(f"[Filtrage IA][DEBUG] === Fin du prompt ===")

        try:
            response = self.client.chat(messages)

            if self.debug:
                print(f"\n[Filtrage IA][DEBUG] === Réponse brute de l'IA pour la mise à jour des étiquettes ===")
                self._print_formatted_json(response)
                print(f"[Filtrage IA][DEBUG] === Fin de la réponse ===")

            result = self._parse_update_tags_response(response)
            if result is None:
                return None

            keep_count = len(result.get("keep", []))
            add_count = len(result.get("add", []))
            remove_count = len(result.get("remove", []))
            ratio = result.get("change_ratio", 0)
            print(f"[Filtrage IA] Plan de mise à jour des étiquettes par l'IA : {keep_count} conservée(s), {add_count} ajoutée(s), {remove_count} retirée(s), change_ratio={ratio:.2f}")

            return result
        except Exception as e:
            print(f"[Filtrage IA] Échec de la mise à jour des étiquettes : {type(e).__name__}: {e}")
            return None

    def _parse_update_tags_response(self, response: str) -> Optional[Dict]:
        """Analyse la réponse de l'IA pour la mise à jour des étiquettes"""
        json_str = self._extract_json(response)
        if not json_str:
            print("[Filtrage IA] Impossible d'extraire du JSON de la réponse de mise à jour des étiquettes")
            return None

        data = json.loads(json_str)

        # Vérification des champs requis
        keep = data.get("keep", [])
        add = data.get("add", [])
        remove = data.get("remove", [])
        change_ratio = float(data.get("change_ratio", 0))

        # Vérification du format de keep/add
        validated_keep = []
        for t in keep:
            if isinstance(t, dict) and "tag" in t:
                validated_keep.append({
                    "tag": str(t["tag"]).strip(),
                    "description": str(t.get("description", "")).strip(),
                })

        validated_add = []
        for t in add:
            if isinstance(t, dict) and "tag" in t:
                validated_add.append({
                    "tag": str(t["tag"]).strip(),
                    "description": str(t.get("description", "")).strip(),
                })

        validated_remove = [str(r).strip() for r in remove if r]

        # change_ratio est borné entre 0 et 1
        change_ratio = max(0.0, min(1.0, change_ratio))

        return {
            "keep": validated_keep,
            "add": validated_add,
            "remove": validated_remove,
            "change_ratio": change_ratio,
        }

    def _parse_tags_response(self, response: str) -> List[Dict]:
        """Analyse la réponse de l'IA pour l'extraction d'étiquettes"""
        json_str = self._extract_json(response)
        if not json_str:
            return []

        data = json.loads(json_str)
        tags_raw = data.get("tags", [])

        tags = []
        for t in tags_raw:
            if not isinstance(t, dict) or "tag" not in t:
                continue
            tags.append({
                "tag": str(t["tag"]).strip(),
                "description": str(t.get("description", "")).strip(),
            })

        return tags

    def classify_batch(
        self,
        titles: List[Dict],
        tags: List[Dict],
        interests_content: str = "",
    ) -> List[Dict]:
        """
        Étape B : classification d'un lot de titres d'actualités

        Args:
            titles: [{"id": news_item_id, "title": str, "source": str}]
            tags: [{"id": tag_id, "tag": str, "description": str}]
            interests_content: description des centres d'intérêt de l'utilisateur (incluant les exigences de filtrage qualitatif)

        Returns:
            [{"news_item_id": int, "tag_id": int, "relevance_score": float}, ...]
        """
        if not titles or not tags:
            return []

        if not self.classify_user:
            print("[Filtrage IA] Le modèle de prompt de classification est vide")
            return []

        # Construction du texte de la liste des étiquettes
        tags_list = "\n".join(
            f"{t['id']}. {t['tag']}: {t.get('description', '')}"
            for t in tags
        )

        # Construction du texte de la liste des actualités
        news_list = "\n".join(
            f"{t['id']}. [{t.get('source', '')}] {t['title']}"
            for t in titles
        )

        # Remplissage du modèle
        user_prompt = self.classify_user
        user_prompt = user_prompt.replace("{interests_content}", interests_content)
        user_prompt = user_prompt.replace("{tags_list}", tags_list)
        user_prompt = user_prompt.replace("{news_count}", str(len(titles)))
        user_prompt = user_prompt.replace("{news_list}", news_list)

        messages = []
        if self.classify_system:
            messages.append({"role": "system", "content": self.classify_system})
        messages.append({"role": "user", "content": user_prompt})

        if self.debug:
            print(f"\n[Filtrage IA][DEBUG] === Prompt de classification (nombre de titres={len(titles)}, étiquettes={len(tags)}) ===")
            for m in messages:
                role = m['role']
                content = m['content']
                # On tronque les listes d'actualités trop longues : on n'affiche que les 5 premières et les 5 dernières entrées
                lines = content.split('\n')
                # On repère la zone de la liste des actualités et on la tronque
                if len(lines) > 30:
                    # Affichage des 15 premières lignes + mention d'omission + 10 dernières lignes
                    head = lines[:15]
                    tail = lines[-10:]
                    omitted = len(lines) - 25
                    truncated = '\n'.join(head) + f'\n... ({omitted} ligne(s) omise(s)) ...\n' + '\n'.join(tail)
                    print(f"[{role}]\n{truncated}")
                else:
                    print(f"[{role}]\n{content}")
            print(f"[Filtrage IA][DEBUG] === Fin du prompt (longueur : {sum(len(m['content']) for m in messages)} caractères) ===")

        try:
            response = self.client.chat(messages)

            return self._parse_classify_response(response, titles, tags)
        except Exception as e:
            print(f"[Filtrage IA] Échec de la requête de classification : {type(e).__name__}: {e}")
            return []

    def _parse_classify_response(
        self,
        response: str,
        titles: List[Dict],
        tags: List[Dict],
    ) -> List[Dict]:
        """Analyse la réponse de l'IA pour la classification

        Prend en charge deux formats JSON :
        - nouveau format (à plat) : [{"id": 1, "tag_id": 1, "score": 0.9}, ...]
        - ancien format (imbriqué) : [{"id": 1, "tags": [{"tag_id": 1, "score": 0.9}]}, ...]

        Chaque actualité ne conserve que l'étiquette au score le plus élevé, ce qui évite qu'une même entrée apparaisse sous plusieurs étiquettes.
        """
        json_str = self._extract_json(response)
        if not json_str:
            if self.debug:
                print(f"[Filtrage IA][DEBUG] Impossible d'extraire du JSON de la réponse de classification ; 500 premiers caractères de la réponse brute : {(response or '')[:500]}")
            return []

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            if self.debug:
                print(f"[Filtrage IA][DEBUG] Échec de l'analyse JSON de la réponse de classification : {e}")
                print(f"[Filtrage IA][DEBUG] 500 premiers caractères du texte JSON extrait : {json_str[:500]}")
            return []

        if not isinstance(data, list):
            if self.debug:
                print(f"[Filtrage IA][DEBUG] Le niveau supérieur de la réponse de classification n'est pas un tableau ; type réel : {type(data).__name__}")
            return []

        # Construction des correspondances d'identifiants
        title_ids = {t["id"] for t in titles}
        title_map = {t["id"]: t["title"] for t in titles}
        tag_id_set = {t["id"] for t in tags}
        tag_name_map = {t["id"]: t["tag"] for t in tags}

        # Chaque actualité ne conserve que l'étiquette au score le plus élevé
        best_per_news: Dict[int, Dict] = {}  # news_id -> {"tag_id": ..., "score": ...}
        skipped_news_ids = 0
        skipped_tag_ids = 0
        skipped_empty = 0

        for item in data:
            if not isinstance(item, dict):
                continue
            news_id = item.get("id")
            if news_id not in title_ids:
                skipped_news_ids += 1
                continue

            # On rassemble toutes les étiquettes candidates pour cette actualité
            candidates = []

            if "tag_id" in item:
                # Nouveau format (à plat) : {"id": 1, "tag_id": 1, "score": 0.9}
                candidates.append({"tag_id": item["tag_id"], "score": item.get("score", 0.5)})
            elif "tags" in item:
                # Ancien format (imbriqué) : {"id": 1, "tags": [{"tag_id": 1, "score": 0.9}]}
                matched_tags = item.get("tags", [])
                if isinstance(matched_tags, list):
                    if not matched_tags:
                        skipped_empty += 1
                        continue
                    candidates.extend(matched_tags)

            if not candidates:
                skipped_empty += 1
                continue

            # On retient l'étiquette valide au score le plus élevé
            best_tag_id = None
            best_score = -1.0

            for tag_match in candidates:
                if not isinstance(tag_match, dict):
                    continue
                tag_id = tag_match.get("tag_id")
                if tag_id not in tag_id_set:
                    skipped_tag_ids += 1
                    continue

                score = tag_match.get("score", 0.5)
                try:
                    score = float(score)
                    score = max(0.0, min(1.0, score))
                except (ValueError, TypeError):
                    score = 0.5

                if score > best_score:
                    best_score = score
                    best_tag_id = tag_id

            if best_tag_id is not None:
                # Si une même actualité est renvoyée plusieurs fois, on ne conserve que le score le plus élevé
                existing = best_per_news.get(news_id)
                if existing is None or best_score > existing["relevance_score"]:
                    best_per_news[news_id] = {
                        "news_item_id": news_id,
                        "tag_id": best_tag_id,
                        "relevance_score": best_score,
                    }

        results = list(best_per_news.values())

        if self.debug:
            ai_returned = len(data)
            print(f"[Filtrage IA][DEBUG] --- Résultat de l'analyse de la classification ---")
            print(f"[Filtrage IA][DEBUG] L'IA a renvoyé {ai_returned} entrée(s), {len(results)} valide(s) (chaque actualité ne conserve que l'étiquette au score le plus élevé)")
            if skipped_empty > 0:
                print(f"[Filtrage IA][DEBUG] Étiquettes vides ignorées : {skipped_empty} entrée(s)")
            if skipped_news_ids > 0:
                print(f"[Filtrage IA][DEBUG] !! news_id invalides ignorés : {skipped_news_ids} entrée(s)")
            if skipped_tag_ids > 0:
                print(f"[Filtrage IA][DEBUG] !! tag_id invalides ignorés : {skipped_tag_ids} entrée(s)")

            # Synthèse par étiquette
            tag_summary: Dict[int, List[str]] = {}
            for r in results:
                tid = r["tag_id"]
                if tid not in tag_summary:
                    tag_summary[tid] = []
                tag_summary[tid].append(
                    f"  [{r['news_item_id']}] {title_map.get(r['news_item_id'], '?')[:40]} (score={r['relevance_score']:.2f})"
                )

            for tid, items in tag_summary.items():
                tname = tag_name_map.get(tid, f"tag_{tid}")
                print(f"[Filtrage IA][DEBUG] Étiquette «{tname}» : {len(items)} correspondance(s) :")
                for line in items:
                    print(line)

        return results

    def _extract_json(self, response: str) -> Optional[str]:
        """Extrait la chaîne JSON de la réponse de l'IA"""
        if not response or not response.strip():
            return None

        json_str = response.strip()

        if "```json" in json_str:
            parts = json_str.split("```json", 1)
            if len(parts) > 1:
                code_block = parts[1]
                end_idx = code_block.find("```")
                json_str = code_block[:end_idx] if end_idx != -1 else code_block
        elif "```" in json_str:
            parts = json_str.split("```", 2)
            if len(parts) >= 2:
                json_str = parts[1]

        json_str = json_str.strip()
        return json_str if json_str else None

    def _print_formatted_json(self, response: str) -> None:
        """Affiche de façon formatée le JSON contenu dans la réponse de l'IA, pour faciliter la lecture en debug"""
        if not response:
            print("(réponse vide)")
            return

        json_str = self._extract_json(response)
        if json_str:
            try:
                data = json.loads(json_str)
                if isinstance(data, list):
                    # Tableau : chaque élément est compressé sur une seule ligne
                    lines = [json.dumps(item, ensure_ascii=False) for item in data]
                    print("[\n  " + ",\n  ".join(lines) + "\n]")
                else:
                    print(json.dumps(data, ensure_ascii=False, indent=2))
                return
            except json.JSONDecodeError:
                pass

        # L'analyse JSON a échoué ; on affiche directement la réponse brute
        print(response)

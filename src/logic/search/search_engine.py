from typing import Optional

from whoosh import scoring
from whoosh.index import FileIndex
from whoosh.qparser import QueryParser
from whoosh.searching import Searcher

import customlogger as logger
from logic.search import indexer


class BaseSearchEngine:
    _searcher: Searcher = None
    _ix: FileIndex = None

    def execute_query(self, query_str: str, limit: int = None):
        query = QueryParser("content", self._ix.schema).parse(query_str)
        results = self._searcher.search(query, limit=limit)
        logger.debug("Query '{}' took {} to run.".format(query_str, results.runtime))
        return results


class SearchEngine(BaseSearchEngine):
    def __init__(self):
        self.refresh_searcher()

    def refresh_searcher(self):
        self._ix = indexer.im.get_index()
        self._searcher = self._ix.searcher(weighting=scoring.TF_IDF())


class SongSearchEngine(BaseSearchEngine):
    def __init__(self):
        self._ix = indexer.im.get_index(song_index=True)
        self._searcher = self._ix.searcher(weighting=scoring.TF_IDF())


def advanced_single_query(query: str, partial_match: bool = True, idolized: bool = True,
                          ssr: bool = True, owned_only: bool = False) -> list[int]:
    query = query.split()
    square_bracket_open = False
    if partial_match:
        for idx in range(len(query)):
            if query[idx].rfind("[") > query[idx].rfind("]"):
                square_bracket_open = True
            if query[idx].rfind("]") > query[idx].rfind("["):
                square_bracket_open = False
            query_temp = handle_query_keywords(query[idx], square_bracket_open)
            if query_temp is not None:
                query[idx] = query_temp
                continue
            if query[idx][-1] == "+":
                continue
            query[idx] += "*"
    query = " ".join(query)
    if idolized:
        query = query + " idolized:true"
    if ssr:
        query = query + " rarity:ssr*"
    if owned_only:
        query = query + " owned:[1 TO]"
    results = engine.execute_query(query)
    if len(results) >= 1:
        return [int(_['title']) for _ in results]
    return []


def song_query(query: str, partial_match: bool = True) -> list[int]:
    query = query.split()
    if partial_match:
        for idx in range(len(query)):
            query_temp = handle_query_keywords(query[idx])
            if query_temp is not None:
                query[idx] = query_temp
                continue
            query[idx] += "*"
    query = " ".join(query)
    results = song_engine.execute_query(query)
    if len(results) >= 1:
        return [int(_['title']) for _ in results]
    return []


def handle_query_keywords(query: str, inside_square_bracket: bool = False) -> Optional[str]:
    if query in ("OR", "AND", "NOT", "TO") or all(c in "()[]" for c in query) \
            or query.endswith("]") or inside_square_bracket:
        return query
    parenthesis_count = 0
    while query.endswith(")"):
        query = query[:-1]
        parenthesis_count += 1
    if parenthesis_count > 0:
        query += "*" + ")" * parenthesis_count
        return query
    else:
        return None


engine = SearchEngine()
song_engine = SongSearchEngine()

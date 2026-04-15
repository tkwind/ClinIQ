from typing import List

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

PUBMED_ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_ESUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
PUBMED_DB = "pubmed"
PUBMED_RETMAX = 30

app = FastAPI(title="ClinIQ - Phase 1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1)


class PubMedResult(BaseModel):
    title: str
    pub_date: str
    source: str = "PubMed"


async def fetch_pubmed_results(query: str) -> List[PubMedResult]:
    params_esearch = {
        "db": PUBMED_DB,
        "term": query,
        "retmode": "json",
        "retmax": PUBMED_RETMAX,
    }

    timeout = httpx.Timeout(15.0)

    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            esearch_resp = await client.get(PUBMED_ESEARCH_URL, params=params_esearch)
            esearch_resp.raise_for_status()
            esearch_data = esearch_resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise HTTPException(status_code=502, detail=f"Failed to fetch PubMed IDs: {exc}") from exc

        id_list = esearch_data.get("esearchresult", {}).get("idlist", [])
        if not id_list:
            return []

        params_esummary = {
            "db": PUBMED_DB,
            "id": ",".join(id_list),
            "retmode": "json",
        }

        try:
            esummary_resp = await client.get(PUBMED_ESUMMARY_URL, params=params_esummary)
            esummary_resp.raise_for_status()
            esummary_data = esummary_resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise HTTPException(status_code=502, detail=f"Failed to fetch PubMed summaries: {exc}") from exc

    result_block = esummary_data.get("result", {})
    uids = result_block.get("uids", [])

    results: List[PubMedResult] = []
    for uid in uids:
        item = result_block.get(uid, {})
        title = item.get("title", "")
        pub_date = item.get("pubdate") or item.get("epubdate") or item.get("sortpubdate") or ""

        if title:
            results.append(PubMedResult(title=title, pub_date=pub_date))

    return results


@app.post("/query", response_model=List[PubMedResult])
async def query_pubmed(payload: QueryRequest) -> List[PubMedResult]:
    query = payload.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query must not be empty")

    return await fetch_pubmed_results(query)

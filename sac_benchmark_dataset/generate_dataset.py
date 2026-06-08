#!/usr/bin/env python3
"""Generate a custom Search-as-Code benchmark dataset.

The dataset is intentionally synthetic but operationally realistic. It is built
to stress the behaviors Search-as-Code should improve:

- fanout over many entities
- joins across account notes, security advisories, tickets, and releases
- exact-token lookup for CVEs, ticket IDs, versions, and customer names
- metadata filtering by severity, date, product, vertical, and owner
- reflection when the evidence pool is thin or a negative answer is required
- budget control before reranking
"""

from __future__ import annotations

from collections import Counter, defaultdict
import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
BEIR_DIR = DATA_DIR / "beir"
VERSION = "sac-codegen-v2"


def main() -> None:
    documents = build_documents()
    tasks = build_tasks()
    write_jsonl(DATA_DIR / "corpus.jsonl", documents)
    write_jsonl(DATA_DIR / "tasks.jsonl", tasks)
    write_jsonl(DATA_DIR / "hard_negatives.jsonl", build_hard_negative_rows(tasks))
    write_json(DATA_DIR / "manifest.json", build_manifest(documents, tasks))
    write_beir(documents, tasks)
    print_summary(documents, tasks)


def build_documents() -> list[dict]:
    docs: list[dict] = []

    def add(doc_id: str, title: str, body: str, **metadata: object) -> None:
        docs.append(
            {
                "doc_id": doc_id,
                "title": title,
                "text": body.strip(),
                "metadata": {
                    "dataset_version": VERSION,
                    **metadata,
                },
            }
        )

    vulnerabilities = [
        {
            "slug": "atlas-saml-4102",
            "cve": "CVE-2026-4102",
            "product": "AtlasSearch",
            "component": "Kestrel SAML connector",
            "cvss": 9.4,
            "severity": "critical",
            "disclosed": "2026-05-14",
            "fixed_version": "4.8.2",
            "ticket": "SEC-1842",
            "owner": "Mina Patel",
            "mitigation": "disable the legacy SAML parser and require signed metadata refresh",
            "customers": ["Northwind Health", "Riverline Logistics"],
        },
        {
            "slug": "meridian-path-2899",
            "cve": "CVE-2026-2899",
            "product": "Meridian Sync",
            "component": "export bundle service",
            "cvss": 9.1,
            "severity": "critical",
            "disclosed": "2026-04-27",
            "fixed_version": "2.7.5",
            "ticket": "SEC-1775",
            "owner": "Jon Bell",
            "mitigation": "disable nested archive export for untrusted workspaces",
            "customers": ["Aster Bank", "Riverline Logistics"],
        },
        {
            "slug": "forge-ssrf-1984",
            "cve": "CVE-2026-1984",
            "product": "ForgeDeploy",
            "component": "webhook preview renderer",
            "cvss": 9.8,
            "severity": "critical",
            "disclosed": "2026-03-19",
            "fixed_version": "6.2.0",
            "ticket": "SEC-1690",
            "owner": "Priya Rao",
            "mitigation": "block link preview fetches to private IP ranges",
            "customers": ["HelioGrid Energy", "Greenhouse University"],
        },
        {
            "slug": "beacon-oauth-3771",
            "cve": "CVE-2026-3771",
            "product": "Beacon CRM Connector",
            "component": "OAuth refresh token cache",
            "cvss": 8.7,
            "severity": "high",
            "disclosed": "2026-05-02",
            "fixed_version": "3.14.1",
            "ticket": "SEC-1811",
            "owner": "Luis Romero",
            "mitigation": "rotate connector secrets and enable single-use refresh tokens",
            "customers": ["Contoso Retail", "UrbanNest"],
        },
        {
            "slug": "atlas-rerank-4520",
            "cve": "CVE-2026-4520",
            "product": "AtlasSearch",
            "component": "rerank cache",
            "cvss": 8.9,
            "severity": "high",
            "disclosed": "2026-05-28",
            "fixed_version": "4.9.0",
            "ticket": "SEC-1899",
            "owner": "Mina Patel",
            "mitigation": "flush shared rerank cache and pin cache namespace per tenant",
            "customers": ["BluePeak Insurance", "QuartzBio Labs"],
        },
        {
            "slug": "compass-csv-1440",
            "cve": "CVE-2026-1440",
            "product": "Compass Analytics",
            "component": "CSV export",
            "cvss": 6.4,
            "severity": "medium",
            "disclosed": "2026-02-11",
            "fixed_version": "1.19.3",
            "ticket": "SEC-1604",
            "owner": "Ava Chen",
            "mitigation": "prefix spreadsheet formulas with a safe quote character",
            "customers": ["NovaFoods", "BluePeak Insurance"],
        },
    ]

    for vuln in vulnerabilities:
        add(
            f"adv-{vuln['slug']}",
            f"{vuln['product']} advisory for {vuln['cve']}",
            f"""
            Vendor advisory: {vuln['cve']} affects {vuln['product']} in the {vuln['component']}.
            Severity is {vuln['severity']} with CVSS {vuln['cvss']}. Disclosure date: {vuln['disclosed']}.
            Fixed version: {vuln['fixed_version']}. Recommended mitigation: {vuln['mitigation']}.
            Known exposed customers: {', '.join(vuln['customers'])}. Security owner: {vuln['owner']}.
            """,
            source="vendor_advisory",
            doc_type="security_advisory",
            product=vuln["product"],
            component=vuln["component"],
            cve=vuln["cve"],
            severity=vuln["severity"],
            cvss=vuln["cvss"],
            date=vuln["disclosed"],
            fixed_version=vuln["fixed_version"],
            owner=vuln["owner"],
        )
        add(
            f"ticket-{vuln['ticket'].lower()}",
            f"{vuln['ticket']} internal security response for {vuln['cve']}",
            f"""
            Internal ticket {vuln['ticket']} tracks response to {vuln['cve']} for {vuln['product']}.
            Owner: {vuln['owner']}. Required action: ship {vuln['fixed_version']}, notify customers,
            and confirm mitigation: {vuln['mitigation']}. Customers in scope: {', '.join(vuln['customers'])}.
            Status: patch available, customer rollout not fully complete.
            """,
            source="jira",
            doc_type="security_ticket",
            product=vuln["product"],
            cve=vuln["cve"],
            severity=vuln["severity"],
            ticket=vuln["ticket"],
            date=vuln["disclosed"],
            owner=vuln["owner"],
        )

    releases = [
        {
            "doc_id": "rel-atlas-4-8-2",
            "product": "AtlasSearch",
            "version": "4.8.2",
            "date": "2026-05-16",
            "owner": "Mina Patel",
            "fixes": ["CVE-2026-4102"],
            "features": ["Exact Token Guard", "SAML metadata refresh audit log"],
            "latency": "p95 query latency unchanged at 280 ms",
        },
        {
            "doc_id": "rel-atlas-4-9-0",
            "product": "AtlasSearch",
            "version": "4.9.0",
            "date": "2026-06-01",
            "owner": "Mina Patel",
            "fixes": ["CVE-2026-4520"],
            "features": ["Evidence Ledger", "tenant-scoped rerank cache"],
            "latency": "p95 rerank latency increased by 18 ms when Evidence Ledger is enabled",
        },
        {
            "doc_id": "rel-meridian-2-7-5",
            "product": "Meridian Sync",
            "version": "2.7.5",
            "date": "2026-05-03",
            "owner": "Jon Bell",
            "fixes": ["CVE-2026-2899", "EXPORT-LAT-77"],
            "features": ["archive path normalization", "parallel export chunking"],
            "latency": "large export p95 dropped from 14.8 minutes to 3.9 minutes",
        },
        {
            "doc_id": "rel-forge-6-2-0",
            "product": "ForgeDeploy",
            "version": "6.2.0",
            "date": "2026-03-22",
            "owner": "Priya Rao",
            "fixes": ["CVE-2026-1984"],
            "features": ["webhook preview allowlist", "private network egress block"],
            "latency": "no deployment latency regression",
        },
        {
            "doc_id": "rel-beacon-3-14-1",
            "product": "Beacon CRM Connector",
            "version": "3.14.1",
            "date": "2026-05-06",
            "owner": "Luis Romero",
            "fixes": ["CVE-2026-3771"],
            "features": ["single-use refresh tokens", "connector secret rotation workflow"],
            "latency": "token exchange p95 increased by 11 ms",
        },
        {
            "doc_id": "rel-compass-1-19-3",
            "product": "Compass Analytics",
            "version": "1.19.3",
            "date": "2026-02-14",
            "owner": "Ava Chen",
            "fixes": ["CVE-2026-1440"],
            "features": ["safe CSV export"],
            "latency": "export latency unchanged",
        },
        {
            "doc_id": "rel-rovo-5-3-0",
            "product": "Rovo Chat",
            "version": "5.3.0",
            "date": "2026-05-21",
            "owner": "Nora Singh",
            "fixes": ["SEARCH-217"],
            "features": ["Search-as-Code experimental mode", "tool trace compaction"],
            "latency": "agent trace token volume reduced by 31 percent in pilot",
        },
    ]

    for rel in releases:
        add(
            rel["doc_id"],
            f"{rel['product']} {rel['version']} release notes",
            f"""
            Release notes for {rel['product']} {rel['version']} on {rel['date']}.
            Owner: {rel['owner']}. Fixes: {', '.join(rel['fixes'])}.
            New capabilities: {', '.join(rel['features'])}. Performance note: {rel['latency']}.
            Rollout rule: regulated customers require security approval before production upgrade.
            """,
            source="release_notes",
            doc_type="release",
            product=rel["product"],
            version=rel["version"],
            date=rel["date"],
            owner=rel["owner"],
            fixes=rel["fixes"],
        )

    customers = [
        {
            "slug": "northwind",
            "name": "Northwind Health",
            "vertical": "healthcare",
            "arr": "$4.8M",
            "renewal": "2026-06-25",
            "products": ["AtlasSearch", "Rovo Chat"],
            "blocker": "SAML audit evidence is blocked by CVE-2026-4102 rollout",
            "issue": "SEC-1842",
            "owner": "Mina Patel",
            "csm": "Eli Grant",
            "risk": "red",
            "next": "ship AtlasSearch 4.8.2 to staging and send signed metadata audit log",
        },
        {
            "slug": "aster",
            "name": "Aster Bank",
            "vertical": "financial_services",
            "arr": "$7.2M",
            "renewal": "2026-06-18",
            "products": ["Meridian Sync", "Compass Analytics"],
            "blocker": "quarterly export package times out during audit review",
            "issue": "EXPORT-LAT-77",
            "owner": "Jon Bell",
            "csm": "Maya Brooks",
            "risk": "red",
            "next": "upgrade to Meridian Sync 2.7.5 and rerun the audit export",
        },
        {
            "slug": "contoso",
            "name": "Contoso Retail",
            "vertical": "retail",
            "arr": "$2.1M",
            "renewal": "2026-07-08",
            "products": ["Beacon CRM Connector", "Rovo Chat"],
            "blocker": "CRM security review is waiting on OAuth token replay fix",
            "issue": "SEC-1811",
            "owner": "Luis Romero",
            "csm": "Rhea Park",
            "risk": "amber",
            "next": "rotate connector secret after Beacon CRM Connector 3.14.1 upgrade",
        },
        {
            "slug": "heliogrid",
            "name": "HelioGrid Energy",
            "vertical": "energy",
            "arr": "$5.6M",
            "renewal": "2026-06-30",
            "products": ["ForgeDeploy", "AtlasSearch"],
            "blocker": "deployment audit requires proof that webhook SSRF is fixed",
            "issue": "SEC-1690",
            "owner": "Priya Rao",
            "csm": "Noah Kim",
            "risk": "red",
            "next": "attach ForgeDeploy 6.2.0 egress block evidence to the audit packet",
        },
        {
            "slug": "bluepeak",
            "name": "BluePeak Insurance",
            "vertical": "insurance",
            "arr": "$3.9M",
            "renewal": "2026-07-02",
            "products": ["AtlasSearch", "Compass Analytics"],
            "blocker": "tenant isolation review is blocked by rerank cache evidence",
            "issue": "SEC-1899",
            "owner": "Mina Patel",
            "csm": "Owen Hart",
            "risk": "amber",
            "next": "enable AtlasSearch 4.9.0 Evidence Ledger in staging",
        },
        {
            "slug": "quartzbio",
            "name": "QuartzBio Labs",
            "vertical": "life_sciences",
            "arr": "$6.3M",
            "renewal": "2026-07-11",
            "products": ["AtlasSearch", "Meridian Sync"],
            "blocker": "regulated data review asks for rerank cache namespace proof",
            "issue": "SEC-1899",
            "owner": "Mina Patel",
            "csm": "Iris Zhao",
            "risk": "amber",
            "next": "send Evidence Ledger sample and cache namespace design note",
        },
        {
            "slug": "riverline",
            "name": "Riverline Logistics",
            "vertical": "logistics",
            "arr": "$1.8M",
            "renewal": "2026-06-20",
            "products": ["AtlasSearch", "Meridian Sync"],
            "blocker": "two security exceptions remain open: SAML connector and export path traversal",
            "issue": "SEC-1842 SEC-1775",
            "owner": "Mina Patel and Jon Bell",
            "csm": "Tara Singh",
            "risk": "red",
            "next": "complete AtlasSearch 4.8.2 and Meridian Sync 2.7.5 rollout before renewal call",
        },
        {
            "slug": "urbannest",
            "name": "UrbanNest",
            "vertical": "real_estate",
            "arr": "$1.4M",
            "renewal": "2026-08-06",
            "products": ["Beacon CRM Connector", "Rovo Chat"],
            "blocker": "CRM connector rotation plan is incomplete but renewal is not urgent",
            "issue": "SEC-1811",
            "owner": "Luis Romero",
            "csm": "Rhea Park",
            "risk": "green",
            "next": "schedule Beacon CRM Connector 3.14.1 rollout in July maintenance window",
        },
        {
            "slug": "novafoods",
            "name": "NovaFoods",
            "vertical": "food_services",
            "arr": "$900K",
            "renewal": "2026-09-14",
            "products": ["Compass Analytics"],
            "blocker": "CSV formula injection patch is requested but not renewal blocking",
            "issue": "SEC-1604",
            "owner": "Ava Chen",
            "csm": "Owen Hart",
            "risk": "green",
            "next": "upgrade Compass Analytics 1.19.3 in the next standard patch window",
        },
        {
            "slug": "greenhouse",
            "name": "Greenhouse University",
            "vertical": "education",
            "arr": "$1.2M",
            "renewal": "2026-08-19",
            "products": ["ForgeDeploy"],
            "blocker": "procurement asks whether ForgeDeploy webhook SSRF is fixed",
            "issue": "SEC-1690",
            "owner": "Priya Rao",
            "csm": "Eli Grant",
            "risk": "amber",
            "next": "send ForgeDeploy 6.2.0 advisory and egress policy evidence",
        },
    ]

    for cust in customers:
        add(
            f"acct-{cust['slug']}",
            f"{cust['name']} account brief",
            f"""
            Account brief for {cust['name']}. Vertical: {cust['vertical']}. ARR: {cust['arr']}.
            Renewal date: {cust['renewal']}. Products in production: {', '.join(cust['products'])}.
            Renewal risk: {cust['risk']}. CSM: {cust['csm']}. Current blocker: {cust['blocker']}.
            Linked issue(s): {cust['issue']}. Technical owner: {cust['owner']}.
            """,
            source="crm",
            doc_type="account_brief",
            customer=cust["name"],
            vertical=cust["vertical"],
            arr=cust["arr"],
            renewal_date=cust["renewal"],
            products=cust["products"],
            risk=cust["risk"],
            owner=cust["owner"],
        )
        add(
            f"esc-{cust['slug']}",
            f"{cust['name']} escalation and blocker log",
            f"""
            Escalation log for {cust['name']}. Open blocker: {cust['blocker']}.
            Account owner: {cust['csm']}. Technical owner: {cust['owner']}.
            Next action: {cust['next']}. Status: open until evidence is sent and customer confirms acceptance.
            """,
            source="support",
            doc_type="escalation",
            customer=cust["name"],
            renewal_date=cust["renewal"],
            products=cust["products"],
            risk=cust["risk"],
            owner=cust["owner"],
            issue=cust["issue"],
        )
        add(
            f"meet-{cust['slug']}",
            f"{cust['name']} renewal meeting notes",
            f"""
            Renewal meeting notes for {cust['name']}. Customer asked for evidence related to {cust['blocker']}.
            Decision: proceed only after the owner completes: {cust['next']}.
            Commercial note: {cust['arr']} ARR remains in forecast, but risk is {cust['risk']}.
            """,
            source="meeting_notes",
            doc_type="meeting_note",
            customer=cust["name"],
            renewal_date=cust["renewal"],
            products=cust["products"],
            risk=cust["risk"],
            owner=cust["owner"],
        )

    add(
        "roadmap-rovo-sac",
        "Rovo Chat Search-as-Code pilot plan",
        """
        Rovo Chat 5.3.0 includes Search-as-Code experimental mode. The pilot exposes
        query understanding, entity linking, hybrid search, BM25 search, dense search,
        rerank, and evidence compaction as a sandboxed Python SDK. Pilot guardrails:
        maximum two generated programs per user request, maximum 60 rerank candidates,
        and no write actions without approval.
        """,
        source="roadmap",
        doc_type="roadmap",
        product="Rovo Chat",
        date="2026-05-21",
        owner="Nora Singh",
    )
    add(
        "eval-sac-policy",
        "Search-as-Code evaluation policy",
        """
        Search-as-Code evals must compare four systems: fixed enriched retrieval,
        multi-turn tool calling, one-shot generated code, and reflective generated code.
        Required metrics: answer correctness, citation correctness, retrieval recall,
        latency including code generation, token cost, tool calls, rerank pairs,
        invalid code rate, and reflection trigger precision.
        """,
        source="eval_policy",
        doc_type="policy",
        product="Rovo Chat",
        date="2026-05-23",
        owner="Nora Singh",
    )
    add(
        "runbook-regulated-upgrade",
        "Regulated customer upgrade runbook",
        """
        Regulated customers include healthcare, financial services, insurance, energy,
        education, and life sciences. Before production upgrade, send advisory, release
        notes, owner signoff, and customer-specific evidence. Security critical issues
        require patch confirmation before renewal calls inside a 30 day window.
        """,
        source="runbook",
        doc_type="runbook",
        date="2026-05-20",
        owner="Security PMO",
    )
    add(
        "negative-forgedeploy-novafoods",
        "NovaFoods product footprint clarification",
        """
        NovaFoods has no ForgeDeploy workspace, no AtlasSearch tenant, and no Meridian Sync
        deployment. The only active product is Compass Analytics. Security questions about
        ForgeDeploy or AtlasSearch should not be attributed to NovaFoods unless a new
        implementation record appears.
        """,
        source="crm",
        doc_type="product_footprint",
        customer="NovaFoods",
        products=["Compass Analytics"],
        date="2026-05-30",
        owner="Owen Hart",
    )
    add(
        "rel-atlas-4-8-1",
        "AtlasSearch 4.8.1 release notes",
        """
        AtlasSearch 4.8.1 improved synonym expansion and reduced dense retrieval memory use.
        It did not fix CVE-2026-4102 and should not be used as SAML connector remediation.
        """,
        source="release_notes",
        doc_type="release",
        product="AtlasSearch",
        version="4.8.1",
        date="2026-05-09",
        owner="Mina Patel",
    )
    add(
        "rel-meridian-2-7-4",
        "Meridian Sync 2.7.4 release notes",
        """
        Meridian Sync 2.7.4 changed export progress logging. It did not fix
        CVE-2026-2899 or EXPORT-LAT-77. Aster Bank remains blocked until 2.7.5.
        """,
        source="release_notes",
        doc_type="release",
        product="Meridian Sync",
        version="2.7.4",
        date="2026-04-21",
        owner="Jon Bell",
    )
    add(
        "rel-beacon-3-14-0",
        "Beacon CRM Connector 3.14.0 release notes",
        """
        Beacon CRM Connector 3.14.0 added CRM field mapping diagnostics. It did not fix
        CVE-2026-3771 and does not include single-use refresh tokens.
        """,
        source="release_notes",
        doc_type="release",
        product="Beacon CRM Connector",
        version="3.14.0",
        date="2026-04-28",
        owner="Luis Romero",
    )
    add(
        "distractor-general-saml",
        "General SAML onboarding guide",
        """
        The SAML onboarding guide describes certificate upload, metadata URL validation,
        and assertion mapping. It is not a security advisory and does not mention
        CVE-2026-4102, AtlasSearch 4.8.2, or SEC-1842.
        """,
        source="docs",
        doc_type="guide",
        product="AtlasSearch",
        date="2026-01-12",
        owner="Identity Platform",
    )

    for spec in build_distractor_documents():
        add(**spec)

    return docs


def build_distractor_documents() -> list[dict]:
    """Build semantically close distractors for retrieval stress testing."""
    specs: list[dict] = []

    def spec(doc_id: str, title: str, body: str, **metadata: object) -> None:
        specs.append(
            {
                "doc_id": doc_id,
                "title": title,
                "body": body,
                **metadata,
            }
        )

    products = [
        "AtlasSearch",
        "Meridian Sync",
        "ForgeDeploy",
        "Beacon CRM Connector",
        "Compass Analytics",
        "Rovo Chat",
    ]
    owners = ["Mina Patel", "Jon Bell", "Priya Rao", "Luis Romero", "Ava Chen", "Nora Singh"]
    components = {
        "AtlasSearch": ["SAML connector", "rerank cache", "hybrid retriever", "metadata filter", "query rewrite service"],
        "Meridian Sync": ["export service", "archive unpacker", "workspace sync", "audit packet builder", "chunk scheduler"],
        "ForgeDeploy": ["webhook renderer", "rollout planner", "preview service", "deployment token store", "policy engine"],
        "Beacon CRM Connector": ["OAuth cache", "field mapper", "webhook receiver", "secret rotation flow", "CRM sync worker"],
        "Compass Analytics": ["CSV export", "dashboard cache", "metric compiler", "formula sanitizer", "warehouse connector"],
        "Rovo Chat": ["tool trace", "agent memory", "search mode router", "prompt compactor", "sandbox adapter"],
    }

    # Nearby release notes. These are hard because versions and product names are
    # close to the relevant evidence, but most do not contain the target fixes.
    for product_index, product in enumerate(products):
        owner = owners[product_index]
        for minor in range(1, 15):
            version_major = {
                "AtlasSearch": "4",
                "Meridian Sync": "2",
                "ForgeDeploy": "6",
                "Beacon CRM Connector": "3",
                "Compass Analytics": "1",
                "Rovo Chat": "5",
            }[product]
            version = f"{version_major}.{7 + (minor % 4)}.{minor % 6}"
            doc_id = f"decoy-rel-{slug(product)}-{version.replace('.', '-')}-{minor:02d}"
            feature = components[product][minor % len(components[product])]
            body = f"""
            Release notes for {product} {version}. This release updates the {feature}
            and includes routine reliability improvements. It is a nearby version used
            in search distractor tests. Unless explicitly stated, it does not remediate
            CVE-2026-4102, CVE-2026-2899, CVE-2026-1984, CVE-2026-3771, CVE-2026-4520,
            SEC-1842, SEC-1775, SEC-1690, SEC-1811, or SEC-1899. Owner: {owner}.
            """
            spec(
                doc_id,
                f"{product} {version} maintenance release",
                body,
                source="release_notes",
                doc_type="release_distractor",
                product=product,
                version=version,
                date=f"2026-{1 + (minor % 6):02d}-{10 + (minor % 18):02d}",
                owner=owner,
            )

    # Security advisory and ticket distractors with close CVE and ticket IDs.
    severities = ["low", "medium", "high", "critical"]
    for product_index, product in enumerate(products):
        owner = owners[product_index]
        for idx in range(1, 17):
            cve = f"CVE-2026-{1000 + product_index * 700 + idx * 17}"
            ticket = f"SEC-{1200 + product_index * 140 + idx}"
            severity = severities[(idx + product_index) % len(severities)]
            cvss = round(4.1 + ((idx * 7 + product_index) % 55) / 10, 1)
            component = components[product][idx % len(components[product])]
            customer_hint = ["Northwind Health", "Aster Bank", "HelioGrid Energy", "BluePeak Insurance", "NovaFoods"][idx % 5]
            advisory_body = f"""
            Advisory {cve} affects {product} in the {component}. Severity is {severity}
            with CVSS {cvss}. This is a distractor advisory with wording similar to
            active incidents. It is not the target CVE for the benchmark unless the
            query explicitly names {cve}. Affected pilot customer: {customer_hint}.
            Owner: {owner}. Recommended action: standard patch review.
            """
            spec(
                f"decoy-adv-{slug(product)}-{idx:02d}",
                f"{product} advisory for {cve}",
                advisory_body,
                source="vendor_advisory",
                doc_type="security_advisory_distractor",
                product=product,
                component=component,
                cve=cve,
                severity=severity,
                cvss=cvss,
                date=f"2026-{1 + (idx % 6):02d}-{1 + (idx % 24):02d}",
                owner=owner,
            )
            ticket_body = f"""
            Internal ticket {ticket} tracks {cve} for {product}. The ticket mentions
            common benchmark terms such as renewal risk, evidence packet, customer
            advisory, fixed version, and owner. It is not SEC-1842, SEC-1775, SEC-1690,
            SEC-1811, SEC-1899, or SEC-1604. Owner: {owner}. Status: monitoring.
            """
            spec(
                f"decoy-ticket-{ticket.lower()}",
                f"{ticket} distractor ticket for {cve}",
                ticket_body,
                source="jira",
                doc_type="security_ticket_distractor",
                product=product,
                cve=cve,
                ticket=ticket,
                severity=severity,
                date=f"2026-{1 + (idx % 6):02d}-{2 + (idx % 24):02d}",
                owner=owner,
            )

    # Similar customer account clusters. These make wide fanout and filtering
    # harder because many accounts share products, verticals, risks, dates, and
    # owner names without being the gold evidence.
    prefixes = [
        "Cedar", "Summit", "Arbor", "Pacific", "Pioneer", "Silver", "Cobalt", "Harbor", "Prairie", "Canyon",
        "Lunar", "Redwood", "Granite", "Orchid", "Harborview", "Maple", "SummitView", "Ironwood", "Bayside", "Evergreen",
        "Copper", "Meadow", "Stonegate", "Lighthouse", "Keystone", "Juniper", "Citrine", "Willow", "Apex", "Solstice",
        "Vector", "Nimbus", "Pinnacle", "Horizon", "Fieldstone", "Sierra", "Marble", "Crescent", "Noble", "Vista",
        "Brighton", "Cypress", "Anchor", "Terrace", "Orion", "Magnolia", "Cascade", "Sterling", "Hearth", "Union",
    ]
    suffixes = [
        "Health", "Bank", "Retail", "Energy", "Insurance", "Labs", "Logistics", "University", "Foods", "Manufacturing",
    ]
    verticals = {
        "Health": "healthcare",
        "Bank": "financial_services",
        "Retail": "retail",
        "Energy": "energy",
        "Insurance": "insurance",
        "Labs": "life_sciences",
        "Logistics": "logistics",
        "University": "education",
        "Foods": "food_services",
        "Manufacturing": "manufacturing",
    }
    risks = ["green", "amber", "red"]
    issues = ["SEC-1401", "SEC-1510", "SEC-1722", "EXPORT-LAT-31", "CRM-552", "SEARCH-188", "AUDIT-902"]
    for idx, prefix in enumerate(prefixes):
        suffix = suffixes[idx % len(suffixes)]
        customer = f"{prefix} {suffix}"
        cust_slug = slug(customer)
        product_a = products[idx % len(products)]
        product_b = products[(idx + 2) % len(products)]
        product_list = [product_a, product_b] if idx % 3 != 0 else [product_a]
        risk = risks[idx % len(risks)]
        owner = owners[idx % len(owners)]
        issue = issues[idx % len(issues)]
        renewal = f"2026-{6 + (idx % 4):02d}-{10 + (idx % 19):02d}"
        body_account = f"""
        Account brief for {customer}. Vertical: {verticals[suffix]}. Products in production:
        {', '.join(product_list)}. Renewal date: {renewal}. Renewal risk: {risk}.
        Current blocker references {issue}, but this is a distractor account and not part
        of the gold tasks unless the query explicitly names {customer}. Technical owner:
        {owner}. CSM: synthetic owner {idx:02d}.
        """
        spec(
            f"decoy-acct-{cust_slug}",
            f"{customer} account brief",
            body_account,
            source="crm",
            doc_type="account_brief_distractor",
            customer=customer,
            vertical=verticals[suffix],
            products=product_list,
            risk=risk,
            renewal_date=renewal,
            owner=owner,
        )
        body_escalation = f"""
        Escalation log for {customer}. Open item: review evidence packet for {product_a}
        and {issue}. This note deliberately resembles renewal-blocker language but does
        not mention target tickets SEC-1842, SEC-1775, SEC-1690, SEC-1811, SEC-1899,
        or SEC-1604. Next action: schedule standard review. Owner: {owner}.
        """
        spec(
            f"decoy-esc-{cust_slug}",
            f"{customer} escalation log",
            body_escalation,
            source="support",
            doc_type="escalation_distractor",
            customer=customer,
            products=product_list,
            risk=risk,
            issue=issue,
            owner=owner,
        )
        body_meeting = f"""
        Renewal meeting notes for {customer}. The customer asked about security evidence,
        upgrade timing, and owner assignment. This meeting has similar terms to benchmark
        tasks but the account is outside the labeled gold set. Mentioned product:
        {product_b}. Follow-up owner: {owner}.
        """
        spec(
            f"decoy-meet-{cust_slug}",
            f"{customer} renewal meeting notes",
            body_meeting,
            source="meeting_notes",
            doc_type="meeting_note_distractor",
            customer=customer,
            products=product_list,
            risk=risk,
            renewal_date=renewal,
            owner=owner,
        )

    # Policy, runbook, and guide distractors that use the same evaluation and
    # search terminology without containing the target answers.
    guide_topics = [
        "SAML onboarding", "rerank cache tuning", "OAuth connector setup", "webhook preview policy",
        "CSV export hardening", "agent trace review", "renewal forecast hygiene", "security evidence packet",
        "regulated upgrade checklist", "customer escalation triage", "metadata filter design", "hybrid search tuning",
        "BM25 exact token guardrails", "dense retrieval drift", "release note authoring", "incident severity review",
        "sandbox timeout policy", "codegen repair workflow", "tool-call budget policy", "citation audit guide",
    ]
    for idx in range(1, 61):
        topic = guide_topics[idx % len(guide_topics)]
        product = products[idx % len(products)]
        body = f"""
        Internal guide: {topic}. This document mentions Search-as-Code, tool calling,
        evidence, reranking, release notes, exact tokens, and customer context. It is a
        generic process document for {product}. It does not establish a customer-specific
        blocker or fixed version. Use it as background only when the query asks for policy.
        """
        spec(
            f"decoy-guide-{idx:03d}",
            f"{topic} guide",
            body,
            source="docs",
            doc_type="guide_distractor",
            product=product,
            date=f"2026-{1 + (idx % 6):02d}-{1 + (idx % 25):02d}",
            owner=owners[idx % len(owners)],
        )

    # Enterprise indexes are rarely sparse. A single issue often produces many
    # near-identical artifacts: draft advisories, rollout trackers, account notes,
    # Slack digests, customer emails, duplicate tickets, and stale release docs.
    # These clusters intentionally reuse target names, CVEs, versions, and owners
    # while remaining non-authoritative or stale, so retrieval must separate real
    # evidence from same-topic lookalikes.
    target_incidents = [
        {
            "slug": "atlas-saml-4102",
            "product": "AtlasSearch",
            "component": "Kestrel SAML connector",
            "cve": "CVE-2026-4102",
            "ticket": "SEC-1842",
            "fixed_version": "4.8.2",
            "near_version": "4.8.1",
            "owner": "Mina Patel",
            "customers": ["Northwind Health", "Riverline Logistics"],
            "wrong_customers": ["BluePeak Insurance", "Cedar Health", "Summit Logistics"],
        },
        {
            "slug": "meridian-path-2899",
            "product": "Meridian Sync",
            "component": "export bundle service",
            "cve": "CVE-2026-2899",
            "ticket": "SEC-1775",
            "fixed_version": "2.7.5",
            "near_version": "2.7.4",
            "owner": "Jon Bell",
            "customers": ["Aster Bank", "Riverline Logistics"],
            "wrong_customers": ["QuartzBio Labs", "Pioneer Bank", "Nimbus Logistics"],
        },
        {
            "slug": "forge-ssrf-1984",
            "product": "ForgeDeploy",
            "component": "webhook preview renderer",
            "cve": "CVE-2026-1984",
            "ticket": "SEC-1690",
            "fixed_version": "6.2.0",
            "near_version": "6.1.9",
            "owner": "Priya Rao",
            "customers": ["HelioGrid Energy", "Greenhouse University"],
            "wrong_customers": ["NovaFoods", "Canyon Energy", "Terrace University"],
        },
        {
            "slug": "beacon-oauth-3771",
            "product": "Beacon CRM Connector",
            "component": "OAuth refresh token cache",
            "cve": "CVE-2026-3771",
            "ticket": "SEC-1811",
            "fixed_version": "3.14.1",
            "near_version": "3.14.0",
            "owner": "Luis Romero",
            "customers": ["Contoso Retail", "UrbanNest"],
            "wrong_customers": ["Anchor Retail", "UrbanNorth", "Cobalt Retail"],
        },
        {
            "slug": "atlas-rerank-4520",
            "product": "AtlasSearch",
            "component": "rerank cache",
            "cve": "CVE-2026-4520",
            "ticket": "SEC-1899",
            "fixed_version": "4.9.0",
            "near_version": "4.8.2",
            "owner": "Mina Patel",
            "customers": ["BluePeak Insurance", "QuartzBio Labs"],
            "wrong_customers": ["Northwind Health", "Vector Insurance", "Orchid Labs"],
        },
        {
            "slug": "compass-csv-1440",
            "product": "Compass Analytics",
            "component": "CSV export",
            "cve": "CVE-2026-1440",
            "ticket": "SEC-1604",
            "fixed_version": "1.19.3",
            "near_version": "1.19.2",
            "owner": "Ava Chen",
            "customers": ["NovaFoods", "BluePeak Insurance"],
            "wrong_customers": ["Aster Bank", "Keystone Foods", "Brighton Insurance"],
        },
    ]
    incident_kinds = [
        ("digest", "incident_digest_distractor", "slack"),
        ("rollout", "rollout_note_distractor", "confluence"),
        ("ticket", "security_ticket_distractor", "jira"),
        ("meeting", "meeting_note_distractor", "meeting_notes"),
        ("release", "release_distractor", "release_notes"),
        ("email", "customer_email_distractor", "email"),
        ("approval", "security_approval_distractor", "governance"),
        ("postmortem", "incident_postmortem_distractor", "confluence"),
        ("faq", "guide_distractor", "docs"),
        ("dashboard", "risk_dashboard_distractor", "crm"),
    ]
    stale_states = [
        "draft only; not approved for customer citation",
        "staging-only rollout; production evidence is absent",
        "superseded by the authoritative ticket and release notes",
        "mentions the right CVE but maps it to a nearby non-fixing version",
        "records a pilot conversation, not the current renewal blocker",
        "contains a copied customer list that includes accounts outside scope",
        "uses old severity wording before security review finalization",
        "tracks a duplicate work item that was closed as non-authoritative",
    ]
    for incident in target_incidents:
        for idx in range(60):
            serial = idx + 1
            kind, doc_type, source = incident_kinds[idx % len(incident_kinds)]
            stale_state = stale_states[idx % len(stale_states)]
            customer = (incident["customers"] + incident["wrong_customers"])[idx % 5]
            mentioned_version = incident["near_version"] if idx % 3 == 0 else incident["fixed_version"]
            body = f"""
            Same-topic enterprise artifact for {incident['product']} {incident['component']}.
            It mentions {incident['cve']}, {incident['ticket']}, {mentioned_version},
            {incident['owner']}, and customer {customer}. Status: {stale_state}.
            This document is intentionally similar to the real evidence, but it should
            not be treated as authoritative proof of customer impact, fixed version,
            rollout completion, or renewal-blocker ownership unless a task explicitly
            names this artifact. Authoritative sources remain the primary advisory,
            internal security ticket, release note, account brief, and escalation log.
            """
            spec(
                f"cluster-{incident['slug']}-{kind}-{serial:03d}",
                f"{incident['product']} {incident['cve']} {kind} artifact {serial:03d}",
                body,
                source=source,
                doc_type=doc_type,
                product=incident["product"],
                component=incident["component"],
                cve=incident["cve"],
                ticket=incident["ticket"],
                version=mentioned_version,
                customer=customer,
                date=f"2026-{3 + (idx % 4):02d}-{1 + (idx % 27):02d}",
                owner=incident["owner"],
            )

    core_customers = [
        {"slug": "northwind", "name": "Northwind Health", "products": ["AtlasSearch", "Rovo Chat"], "risk": "red", "renewal": "2026-06-25", "owner": "Mina Patel", "issue": "SEC-1842"},
        {"slug": "aster", "name": "Aster Bank", "products": ["Meridian Sync", "Compass Analytics"], "risk": "red", "renewal": "2026-06-18", "owner": "Jon Bell", "issue": "EXPORT-LAT-77"},
        {"slug": "contoso", "name": "Contoso Retail", "products": ["Beacon CRM Connector", "Rovo Chat"], "risk": "amber", "renewal": "2026-07-08", "owner": "Luis Romero", "issue": "SEC-1811"},
        {"slug": "heliogrid", "name": "HelioGrid Energy", "products": ["ForgeDeploy", "AtlasSearch"], "risk": "red", "renewal": "2026-06-30", "owner": "Priya Rao", "issue": "SEC-1690"},
        {"slug": "bluepeak", "name": "BluePeak Insurance", "products": ["AtlasSearch", "Compass Analytics"], "risk": "amber", "renewal": "2026-07-02", "owner": "Mina Patel", "issue": "SEC-1899"},
        {"slug": "quartzbio", "name": "QuartzBio Labs", "products": ["AtlasSearch", "Meridian Sync"], "risk": "amber", "renewal": "2026-07-11", "owner": "Mina Patel", "issue": "SEC-1899"},
        {"slug": "riverline", "name": "Riverline Logistics", "products": ["AtlasSearch", "Meridian Sync"], "risk": "red", "renewal": "2026-06-20", "owner": "Mina Patel and Jon Bell", "issue": "SEC-1842 SEC-1775"},
        {"slug": "urbannest", "name": "UrbanNest", "products": ["Beacon CRM Connector", "Rovo Chat"], "risk": "green", "renewal": "2026-08-06", "owner": "Luis Romero", "issue": "SEC-1811"},
        {"slug": "novafoods", "name": "NovaFoods", "products": ["Compass Analytics"], "risk": "green", "renewal": "2026-09-14", "owner": "Ava Chen", "issue": "SEC-1604"},
        {"slug": "greenhouse", "name": "Greenhouse University", "products": ["ForgeDeploy"], "risk": "amber", "renewal": "2026-08-19", "owner": "Priya Rao", "issue": "SEC-1690"},
    ]
    customer_kinds = [
        ("crm", "account_brief_distractor", "crm"),
        ("renewal", "meeting_note_distractor", "meeting_notes"),
        ("escalation", "escalation_distractor", "support"),
        ("email", "customer_email_distractor", "email"),
        ("risk", "risk_dashboard_distractor", "crm"),
        ("implementation", "implementation_note_distractor", "services"),
        ("forecast", "forecast_note_distractor", "finance"),
        ("audit", "audit_packet_distractor", "security"),
    ]
    stale_customer_statuses = [
        "stale weekly snapshot before the current escalation was updated",
        "duplicates account facts but omits the current fixed version",
        "mentions a renewal call but not the accepted security evidence",
        "captures a sandbox discussion, not production rollout status",
        "contains a copied owner name but wrong product blocker",
        "has similar risk wording but a different renewal window",
        "summarizes a prior quarter and should not override current account brief",
        "lists requested evidence without confirming whether it is sufficient",
    ]
    for customer in core_customers:
        for idx in range(48):
            serial = idx + 1
            kind, doc_type, source = customer_kinds[idx % len(customer_kinds)]
            product = customer["products"][idx % len(customer["products"])]
            status = stale_customer_statuses[idx % len(stale_customer_statuses)]
            body = f"""
            Account-adjacent artifact for {customer['name']}. Products mentioned:
            {', '.join(customer['products'])}. It references {product}, renewal date
            {customer['renewal']}, risk {customer['risk']}, owner {customer['owner']},
            and issue text {customer['issue']}. Status: {status}. This is deliberately
            close to the core account evidence but should be treated as non-authoritative
            unless the query asks for historical notes or stale snapshots.
            """
            spec(
                f"cluster-customer-{customer['slug']}-{kind}-{serial:03d}",
                f"{customer['name']} {kind} artifact {serial:03d}",
                body,
                source=source,
                doc_type=doc_type,
                customer=customer["name"],
                products=customer["products"],
                risk=customer["risk"],
                renewal_date=customer["renewal"],
                issue=customer["issue"],
                date=f"2026-{2 + (idx % 5):02d}-{1 + (idx % 27):02d}",
                owner=customer["owner"],
            )

    product_kinds = [
        ("release", "release_distractor", "release_notes"),
        ("migration", "guide_distractor", "docs"),
        ("kb", "guide_distractor", "support_kb"),
        ("runbook", "runbook_distractor", "runbook"),
        ("advisory", "security_advisory_distractor", "vendor_advisory"),
        ("rollback", "release_distractor", "release_notes"),
        ("compat", "compatibility_note_distractor", "docs"),
        ("perf", "performance_note_distractor", "observability"),
    ]
    for product_index, product in enumerate(products):
        owner = owners[product_index]
        for idx in range(96):
            serial = idx + 1
            kind, doc_type, source = product_kinds[idx % len(product_kinds)]
            component = components[product][idx % len(components[product])]
            version_major = {
                "AtlasSearch": "4",
                "Meridian Sync": "2",
                "ForgeDeploy": "6",
                "Beacon CRM Connector": "3",
                "Compass Analytics": "1",
                "Rovo Chat": "5",
            }[product]
            version = f"{version_major}.{6 + (idx % 5)}.{idx % 10}"
            body = f"""
            Product knowledge artifact for {product} {version}. Topic: {kind};
            component: {component}; owner: {owner}. It contains common enterprise
            search terms such as rollout, blocker, renewal, advisory, ticket, fixed
            version, customer evidence, and approval. It is same-product background,
            not a labeled answer document for customer-specific security tasks.
            """
            spec(
                f"cluster-product-{slug(product)}-{kind}-{serial:03d}",
                f"{product} {kind} note {version}",
                body,
                source=source,
                doc_type=doc_type,
                product=product,
                component=component,
                version=version,
                date=f"2026-{1 + (idx % 6):02d}-{1 + (idx % 26):02d}",
                owner=owner,
            )

    enterprise_topics = [
        "June critical-patch war room",
        "regulated renewal evidence",
        "customer escalation owner review",
        "Search-as-Code codegen eval",
        "multi-turn tool calling comparison",
        "rerank budget and hard-negative intrusion",
        "agent reflection trigger policy",
        "security advisory citation audit",
        "exact identifier preservation",
        "release note evidence packet",
        "customer-product join workflow",
        "negative evidence stop condition",
    ]
    enterprise_kinds = [
        ("memo", "memo_distractor", "confluence"),
        ("thread", "slack_thread_distractor", "slack"),
        ("review", "review_note_distractor", "docs"),
        ("dashboard", "dashboard_snapshot_distractor", "analytics"),
        ("decision", "decision_log_distractor", "confluence"),
        ("draft", "draft_policy_distractor", "docs"),
    ]
    for idx in range(540):
        serial = idx + 1
        topic = enterprise_topics[idx % len(enterprise_topics)]
        kind, doc_type, source = enterprise_kinds[idx % len(enterprise_kinds)]
        product = products[idx % len(products)]
        owner = owners[idx % len(owners)]
        body = f"""
        Enterprise background artifact about {topic}. It references {product},
        owner {owner}, retrieval quality, customer evidence, blockers, release
        notes, exact identifiers, reranking, reflection, and generated code.
        This document is useful background only; it does not contain the specific
        labeled answer fields for the benchmark's customer, CVE, ticket, fixed
        version, or renewal-window questions.
        """
        spec(
            f"cluster-enterprise-{kind}-{serial:03d}",
            f"{topic} {kind} artifact {serial:03d}",
            body,
            source=source,
            doc_type=doc_type,
            product=product,
            date=f"2026-{1 + (idx % 6):02d}-{1 + (idx % 27):02d}",
            owner=owner,
        )

    return specs


def slug(value: str) -> str:
    return (
        value.lower()
        .replace(" ", "-")
        .replace("/", "-")
        .replace("_", "-")
        .replace("'", "")
        .replace(".", "")
    )


def build_tasks() -> list[dict]:
    tasks: list[dict] = []

    def task(
        task_id: str,
        split: str,
        category: str,
        difficulty: str,
        query: str,
        answer: str,
        evidence: list[str],
        operations: list[str],
        *,
        hard_negatives: list[str] | None = None,
        answer_fields: dict | None = None,
        ideal_routes: list[dict] | None = None,
        should_reflect: bool = False,
        notes: str = "",
    ) -> None:
        tasks.append(
            {
                "task_id": task_id,
                "dataset_version": VERSION,
                "split": split,
                "category": category,
                "difficulty": difficulty,
                "query": query,
                "gold_answer": answer,
                "answer_fields": answer_fields or {},
                "evidence_doc_ids": evidence,
                "hard_negative_doc_ids": hard_negatives or [],
                "required_operations": operations,
                "expected_flow": {
                    "should_reflect": should_reflect,
                    "ideal_search_routes": ideal_routes or [],
                    "rerank_policy": "rerank only merged candidates that can support answer fields",
                },
                "evaluation": {
                    "retrieval_relevance": {doc_id: 2 for doc_id in evidence},
                    "citation_required": True,
                    "answer_correctness_required": True,
                    "notes": notes,
                },
            }
        )

    exact_ops = ["entity_linking", "bm25_exact", "metadata_filter", "join", "rerank"]
    wide_ops = ["fanout_search", "metadata_filter", "join", "aggregate", "rerank"]
    code_ops = ["query_understanding", "query_rewrite", "dynamic_route_selection", "candidate_pruning", "rerank"]
    reflect_ops = ["query_understanding", "evidence_reflection", "followup_code_generation", "join", "rerank"]

    task(
        "sac-001",
        "test",
        "security_fanout_join",
        "hard",
        "For Northwind Health, which critical vulnerabilities affect products they run, what fixed versions are needed, and who owns the rollout?",
        "Northwind Health runs AtlasSearch and Rovo Chat. The critical matching vulnerability is CVE-2026-4102 in the AtlasSearch Kestrel SAML connector. Fixed version is AtlasSearch 4.8.2. Owner is Mina Patel, tracked in SEC-1842.",
        ["acct-northwind", "adv-atlas-saml-4102", "ticket-sec-1842", "rel-atlas-4-8-2", "esc-northwind"],
        wide_ops,
        hard_negatives=["rel-atlas-4-8-1", "distractor-general-saml"],
        answer_fields={"customer": "Northwind Health", "cve": "CVE-2026-4102", "fixed_version": "4.8.2", "owner": "Mina Patel"},
        ideal_routes=[
            {"query": "Northwind Health AtlasSearch CVE critical", "mode": "hybrid", "top_k": 12},
            {"query": "CVE-2026-4102 SEC-1842 AtlasSearch 4.8.2", "mode": "bm25", "top_k": 12},
        ],
    )
    task(
        "sac-002",
        "test",
        "customer_risk_join",
        "hard",
        "Which red-risk customers renewing before July 1 have unresolved security or audit blockers, and what is the next action for each?",
        "Northwind Health, Aster Bank, HelioGrid Energy, and Riverline Logistics are red-risk renewals before 2026-07-01. Next actions: Northwind Health ship AtlasSearch 4.8.2 and send SAML audit evidence; Aster Bank upgrade Meridian Sync 2.7.5 and rerun audit export; HelioGrid Energy attach ForgeDeploy 6.2.0 egress block evidence; Riverline Logistics complete AtlasSearch 4.8.2 and Meridian Sync 2.7.5 rollout.",
        ["acct-northwind", "esc-northwind", "acct-aster", "esc-aster", "acct-heliogrid", "esc-heliogrid", "acct-riverline", "esc-riverline", "runbook-regulated-upgrade"],
        wide_ops,
        hard_negatives=["acct-bluepeak", "acct-contoso", "acct-urbannest"],
        answer_fields={"renewal_before": "2026-07-01", "risk": "red", "customers": ["Northwind Health", "Aster Bank", "HelioGrid Energy", "Riverline Logistics"]},
        ideal_routes=[
            {"query": "red risk renewal before July 1 blocker", "mode": "hybrid", "top_k": 30},
            {"query": "renewal date 2026-06 risk red escalation", "mode": "bm25", "top_k": 30},
        ],
    )
    task(
        "sac-003",
        "dev",
        "release_fix_mapping",
        "medium",
        "Aster Bank export audit is timing out. Which release fixes the blocker and what performance change should we cite?",
        "Aster Bank is blocked by quarterly export package timeouts tied to EXPORT-LAT-77. Meridian Sync 2.7.5 fixes EXPORT-LAT-77 and drops large export p95 from 14.8 minutes to 3.9 minutes.",
        ["acct-aster", "esc-aster", "rel-meridian-2-7-5"],
        code_ops,
        hard_negatives=["rel-meridian-2-7-4", "decoy-rel-meridian-sync-2-8-1-01"],
        answer_fields={"customer": "Aster Bank", "fix": "Meridian Sync 2.7.5", "metric": "14.8 minutes to 3.9 minutes"},
        ideal_routes=[
            {"query": "Aster Bank EXPORT-LAT-77 Meridian Sync", "mode": "bm25", "top_k": 10},
            {"query": "Meridian Sync 2.7.5 export latency", "mode": "hybrid", "top_k": 10},
        ],
    )
    task(
        "sac-004",
        "test",
        "security_fanout_join",
        "hard",
        "For Riverline Logistics, identify every open security exception, its CVE, fixed version, and owner.",
        "Riverline Logistics has two open security exceptions: AtlasSearch CVE-2026-4102 fixed by 4.8.2 owned by Mina Patel, and Meridian Sync CVE-2026-2899 fixed by 2.7.5 owned by Jon Bell.",
        ["acct-riverline", "esc-riverline", "adv-atlas-saml-4102", "ticket-sec-1842", "rel-atlas-4-8-2", "adv-meridian-path-2899", "ticket-sec-1775", "rel-meridian-2-7-5"],
        wide_ops,
        hard_negatives=["rel-atlas-4-8-1", "rel-meridian-2-7-4"],
        answer_fields={"customer": "Riverline Logistics", "cves": ["CVE-2026-4102", "CVE-2026-2899"], "fixed_versions": ["4.8.2", "2.7.5"]},
        ideal_routes=[
            {"query": "Riverline Logistics security exceptions", "mode": "hybrid", "top_k": 20},
            {"query": "SEC-1842 SEC-1775", "mode": "bm25", "top_k": 20},
        ],
    )
    task(
        "sac-005",
        "test",
        "exact_identifier_lookup",
        "medium",
        "SEC-1899 is blocking which customers, which CVE does it track, and what release should they use?",
        "SEC-1899 tracks CVE-2026-4520 in the AtlasSearch rerank cache. It blocks BluePeak Insurance and QuartzBio Labs. The release is AtlasSearch 4.9.0.",
        ["ticket-sec-1899", "adv-atlas-rerank-4520", "rel-atlas-4-9-0", "acct-bluepeak", "acct-quartzbio"],
        exact_ops,
        hard_negatives=["rel-atlas-4-8-2", "rel-atlas-4-8-1"],
        answer_fields={"ticket": "SEC-1899", "cve": "CVE-2026-4520", "customers": ["BluePeak Insurance", "QuartzBio Labs"], "release": "AtlasSearch 4.9.0"},
        ideal_routes=[{"query": "SEC-1899 CVE-2026-4520 AtlasSearch 4.9.0", "mode": "bm25", "top_k": 16}],
    )
    task(
        "sac-006",
        "train",
        "release_fix_mapping",
        "medium",
        "Which release introduced Exact Token Guard, and which CVE fix shipped in the same release?",
        "AtlasSearch 4.8.2 introduced Exact Token Guard and fixed CVE-2026-4102.",
        ["rel-atlas-4-8-2", "adv-atlas-saml-4102"],
        exact_ops,
        hard_negatives=["rel-atlas-4-8-1", "rel-atlas-4-9-0"],
        answer_fields={"feature": "Exact Token Guard", "release": "AtlasSearch 4.8.2", "cve": "CVE-2026-4102"},
        ideal_routes=[{"query": "Exact Token Guard CVE", "mode": "bm25", "top_k": 10}],
    )
    task(
        "sac-007",
        "test",
        "regulated_customer_filter",
        "hard",
        "Among regulated customers, which accounts need a critical security patch before a renewal call inside 30 days?",
        "Northwind Health, Aster Bank, HelioGrid Energy, and Riverline Logistics are regulated, red-risk or critical-patch accounts renewing inside 30 days. Their verticals include healthcare, financial_services, energy, and logistics. Required patches: AtlasSearch 4.8.2 for Northwind Health, Meridian Sync 2.7.5 for Aster Bank, ForgeDeploy 6.2.0 for HelioGrid Energy, and both AtlasSearch 4.8.2 plus Meridian Sync 2.7.5 for Riverline Logistics.",
        ["runbook-regulated-upgrade", "acct-northwind", "adv-atlas-saml-4102", "acct-aster", "adv-meridian-path-2899", "acct-heliogrid", "adv-forge-ssrf-1984", "acct-riverline"],
        wide_ops,
        hard_negatives=["acct-bluepeak", "acct-quartzbio", "acct-greenhouse"],
        answer_fields={"verticals": ["healthcare", "financial_services", "energy", "logistics"], "inside_days": 30},
        ideal_routes=[
            {"query": "regulated customer renewal critical patch before renewal", "mode": "hybrid", "top_k": 35},
            {"query": "CVSS 9 critical renewal 2026-06", "mode": "bm25", "top_k": 25},
        ],
    )
    task(
        "sac-008",
        "dev",
        "negative_evidence",
        "hard",
        "Does NovaFoods need any ForgeDeploy remediation for the June security rollout?",
        "No. NovaFoods has no ForgeDeploy workspace and only runs Compass Analytics. It should not be included in ForgeDeploy remediation unless a new implementation record appears.",
        ["acct-novafoods", "negative-forgedeploy-novafoods", "adv-forge-ssrf-1984"],
        ["entity_linking", "negative_evidence_check", "metadata_filter", "reflection", "citation"],
        hard_negatives=["acct-heliogrid", "acct-greenhouse", "ticket-sec-1690"],
        answer_fields={"customer": "NovaFoods", "forge_deploy": False, "active_product": "Compass Analytics"},
        ideal_routes=[
            {"query": "NovaFoods ForgeDeploy product footprint", "mode": "hybrid", "top_k": 12},
            {"query": "NovaFoods no ForgeDeploy", "mode": "bm25", "top_k": 12},
        ],
        should_reflect=True,
    )
    task(
        "sac-009",
        "test",
        "budget_control",
        "hard",
        "Which AtlasSearch customers are blocked by rerank cache evidence, and which ones need Evidence Ledger rather than Exact Token Guard?",
        "BluePeak Insurance and QuartzBio Labs are blocked by rerank cache evidence. They need AtlasSearch 4.9.0 Evidence Ledger and tenant-scoped rerank cache, not Exact Token Guard from 4.8.2.",
        ["acct-bluepeak", "esc-bluepeak", "acct-quartzbio", "esc-quartzbio", "adv-atlas-rerank-4520", "rel-atlas-4-9-0", "rel-atlas-4-8-2"],
        code_ops,
        hard_negatives=["adv-atlas-saml-4102", "rel-atlas-4-8-1"],
        answer_fields={"customers": ["BluePeak Insurance", "QuartzBio Labs"], "needed_feature": "Evidence Ledger", "not_feature": "Exact Token Guard"},
        ideal_routes=[
            {"query": "rerank cache Evidence Ledger customer", "mode": "hybrid", "top_k": 20},
            {"query": "SEC-1899 AtlasSearch 4.9.0 Evidence Ledger", "mode": "bm25", "top_k": 20},
        ],
    )
    task(
        "sac-010",
        "train",
        "exact_identifier_lookup",
        "medium",
        "CVE-2026-1984 maps to which product, fixed version, and customer audit blockers?",
        "CVE-2026-1984 maps to ForgeDeploy webhook preview renderer, fixed in ForgeDeploy 6.2.0. It is tied to HelioGrid Energy deployment audit and Greenhouse University procurement questions.",
        ["adv-forge-ssrf-1984", "ticket-sec-1690", "rel-forge-6-2-0", "acct-heliogrid", "acct-greenhouse"],
        exact_ops,
        hard_negatives=["adv-beacon-oauth-3771", "rel-beacon-3-14-1", "acct-contoso"],
        answer_fields={"cve": "CVE-2026-1984", "product": "ForgeDeploy", "version": "6.2.0", "customers": ["HelioGrid Energy", "Greenhouse University"]},
        ideal_routes=[{"query": "CVE-2026-1984 ForgeDeploy 6.2.0 HelioGrid Greenhouse", "mode": "bm25", "top_k": 20}],
    )
    task(
        "sac-011",
        "test",
        "tool_calling_vs_codegen",
        "hard",
        "For all customers using both AtlasSearch and Meridian Sync, summarize blockers and do not include customers using only one of those products.",
        "Riverline Logistics and QuartzBio Labs use both AtlasSearch and Meridian Sync. Riverline Logistics has SAML connector and export path traversal exceptions; QuartzBio Labs is blocked by rerank cache namespace proof. Northwind Health, BluePeak Insurance, Aster Bank, and HelioGrid Energy use only one of the two and should not be included.",
        ["acct-riverline", "esc-riverline", "acct-quartzbio", "esc-quartzbio", "adv-atlas-saml-4102", "adv-meridian-path-2899", "adv-atlas-rerank-4520"],
        ["fanout_search", "set_intersection", "negative_filter", "join", "aggregate"],
        hard_negatives=["acct-northwind", "acct-bluepeak", "acct-aster", "acct-heliogrid"],
        answer_fields={"customers": ["Riverline Logistics", "QuartzBio Labs"], "exclude": ["Northwind Health", "BluePeak Insurance", "Aster Bank", "HelioGrid Energy"]},
        ideal_routes=[
            {"query": "AtlasSearch Meridian Sync customers", "mode": "hybrid", "top_k": 30},
            {"query": "products in production AtlasSearch Meridian Sync", "mode": "bm25", "top_k": 30},
        ],
    )
    task(
        "sac-012",
        "dev",
        "reflection_required",
        "hard",
        "If the first search only finds AtlasSearch SAML docs, what additional route should recover Riverline's second blocker?",
        "The follow-up route should search for Riverline Logistics Meridian Sync, SEC-1775, CVE-2026-2899, and Meridian Sync 2.7.5 because Riverline also has an export path traversal exception.",
        ["acct-riverline", "esc-riverline", "adv-meridian-path-2899", "ticket-sec-1775", "rel-meridian-2-7-5"],
        reflect_ops,
        hard_negatives=["adv-atlas-saml-4102", "ticket-sec-1842"],
        answer_fields={"followup_terms": ["Riverline Logistics", "Meridian Sync", "SEC-1775", "CVE-2026-2899", "2.7.5"]},
        ideal_routes=[
            {"query": "Riverline Logistics Meridian Sync SEC-1775 CVE-2026-2899", "mode": "bm25", "top_k": 15},
            {"query": "Riverline export path traversal", "mode": "hybrid", "top_k": 15},
        ],
        should_reflect=True,
    )
    task(
        "sac-013",
        "test",
        "comparative_analysis",
        "medium",
        "Compare Beacon CRM Connector 3.14.0 and 3.14.1 for Contoso's security review. Which one is acceptable?",
        "Beacon CRM Connector 3.14.1 is acceptable because it fixes CVE-2026-3771 with single-use refresh tokens. 3.14.0 only added diagnostics and did not fix the CVE.",
        ["acct-contoso", "esc-contoso", "rel-beacon-3-14-1", "rel-beacon-3-14-0", "adv-beacon-oauth-3771"],
        ["exact_version_compare", "bm25_exact", "join", "rerank"],
        hard_negatives=["rel-atlas-4-8-1", "rel-meridian-2-7-4"],
        answer_fields={"acceptable_version": "3.14.1", "reject_version": "3.14.0", "cve": "CVE-2026-3771"},
        ideal_routes=[{"query": "Beacon CRM Connector 3.14.0 3.14.1 CVE-2026-3771", "mode": "bm25", "top_k": 20}],
    )
    task(
        "sac-014",
        "test",
        "wide_fanout",
        "hard",
        "Find every high or critical CVE disclosed in May 2026, then list exposed customers and fixed versions.",
        "In 2026-05, high or critical CVEs are CVE-2026-4102 fixed in AtlasSearch 4.8.2 affecting Northwind Health and Riverline Logistics; CVE-2026-3771 fixed in Beacon CRM Connector 3.14.1 affecting Contoso Retail and UrbanNest; CVE-2026-4520 fixed in AtlasSearch 4.9.0 affecting BluePeak Insurance and QuartzBio Labs.",
        ["adv-atlas-saml-4102", "rel-atlas-4-8-2", "adv-beacon-oauth-3771", "rel-beacon-3-14-1", "adv-atlas-rerank-4520", "rel-atlas-4-9-0", "ticket-sec-1842", "ticket-sec-1811", "ticket-sec-1899"],
        wide_ops,
        hard_negatives=["adv-meridian-path-2899", "adv-compass-csv-1440", "adv-forge-ssrf-1984"],
        answer_fields={"date_month": "2026-05", "min_severity": "high", "cves": ["CVE-2026-4102", "CVE-2026-3771", "CVE-2026-4520"]},
        ideal_routes=[
            {"query": "disclosed 2026-05 high critical CVE fixed version exposed customers", "mode": "hybrid", "top_k": 40},
            {"query": "CVE-2026 May CVSS fixed version customers", "mode": "bm25", "top_k": 40},
        ],
    )
    task(
        "sac-015",
        "train",
        "policy_lookup",
        "medium",
        "What metrics must a Search-as-Code eval report according to the evaluation policy?",
        "The eval must report answer correctness, citation correctness, retrieval recall, latency including code generation, token cost, tool calls, rerank pairs, invalid code rate, and reflection trigger precision.",
        ["eval-sac-policy", "roadmap-rovo-sac"],
        ["bm25_exact", "policy_lookup"],
        hard_negatives=["runbook-regulated-upgrade", "decoy-guide-018"],
        answer_fields={"metrics": ["answer correctness", "citation correctness", "retrieval recall", "latency including code generation", "token cost", "tool calls", "rerank pairs", "invalid code rate", "reflection trigger precision"]},
        ideal_routes=[{"query": "Search-as-Code evaluation policy metrics", "mode": "bm25", "top_k": 5}],
    )
    task(
        "sac-016",
        "test",
        "reflection_required",
        "hard",
        "A generated flow for a thin-evidence enterprise query finds only 18 candidates. What should the agent do when candidate pool is below 25?",
        "When the condition is candidate pool below 25, it should generate follow-up retrieval code with a larger route budget rather than force all rerank candidates. In this dataset, the policy is to reflect on thin evidence, add targeted hybrid/BM25/dense routes, merge new candidates, and rerank only if new evidence appears.",
        ["roadmap-rovo-sac", "eval-sac-policy"],
        reflect_ops,
        hard_negatives=["decoy-guide-018", "decoy-guide-017", "runbook-regulated-upgrade"],
        answer_fields={"threshold": "candidate pool below 25", "action": "generate follow-up retrieval code"},
        ideal_routes=[{"query": "candidate pool below 25 follow-up code rerank policy", "mode": "hybrid", "top_k": 12}],
        should_reflect=True,
    )

    # Add templated coverage tasks to reach a balanced v1 without weakening the
    # hand-authored core. These still have explicit evidence and answer fields.
    product_tasks = [
        ("sac-017", "dev", "Contoso Retail", "Beacon CRM Connector", "SEC-1811", "CVE-2026-3771", "3.14.1", "Luis Romero", ["acct-contoso", "esc-contoso", "ticket-sec-1811", "adv-beacon-oauth-3771", "rel-beacon-3-14-1"]),
        ("sac-018", "test", "HelioGrid Energy", "ForgeDeploy", "SEC-1690", "CVE-2026-1984", "6.2.0", "Priya Rao", ["acct-heliogrid", "esc-heliogrid", "ticket-sec-1690", "adv-forge-ssrf-1984", "rel-forge-6-2-0"]),
        ("sac-019", "train", "UrbanNest", "Beacon CRM Connector", "SEC-1811", "CVE-2026-3771", "3.14.1", "Luis Romero", ["acct-urbannest", "esc-urbannest", "ticket-sec-1811", "adv-beacon-oauth-3771", "rel-beacon-3-14-1"]),
        ("sac-020", "test", "Greenhouse University", "ForgeDeploy", "SEC-1690", "CVE-2026-1984", "6.2.0", "Priya Rao", ["acct-greenhouse", "esc-greenhouse", "ticket-sec-1690", "adv-forge-ssrf-1984", "rel-forge-6-2-0"]),
        ("sac-021", "dev", "BluePeak Insurance", "AtlasSearch", "SEC-1899", "CVE-2026-4520", "4.9.0", "Mina Patel", ["acct-bluepeak", "esc-bluepeak", "ticket-sec-1899", "adv-atlas-rerank-4520", "rel-atlas-4-9-0"]),
        ("sac-022", "test", "QuartzBio Labs", "AtlasSearch", "SEC-1899", "CVE-2026-4520", "4.9.0", "Mina Patel", ["acct-quartzbio", "esc-quartzbio", "ticket-sec-1899", "adv-atlas-rerank-4520", "rel-atlas-4-9-0"]),
        ("sac-023", "train", "NovaFoods", "Compass Analytics", "SEC-1604", "CVE-2026-1440", "1.19.3", "Ava Chen", ["acct-novafoods", "esc-novafoods", "ticket-sec-1604", "adv-compass-csv-1440", "rel-compass-1-19-3"]),
    ]
    for task_id, split, customer, product, ticket, cve, version, owner, evidence in product_tasks:
        task(
            task_id,
            split,
            "customer_patch_mapping",
            "medium",
            f"For {customer}, map the open blocker to ticket, CVE, fixed version, and technical owner.",
            f"{customer}'s blocker maps to {ticket}, {cve}, fixed by {product} {version}, owned by {owner}.",
            evidence,
            exact_ops,
            hard_negatives=[doc for doc in ["rel-atlas-4-8-1", "rel-meridian-2-7-4", "rel-beacon-3-14-0"] if doc not in evidence],
            answer_fields={"customer": customer, "product": product, "ticket": ticket, "cve": cve, "fixed_version": version, "owner": owner},
            ideal_routes=[{"query": f"{customer} {ticket} {cve} {product} {version}", "mode": "bm25", "top_k": 14}],
        )

    task(
        "sac-024",
        "test",
        "search_as_code_eval_design",
        "hard",
        "Design the minimum comparison table for evaluating whether Search-as-Code is better than a normal agent.",
        "The minimum evaluation table must include fixed enriched retrieval, multi-turn tool calling, one-shot generated code, and reflective generated code. Metrics must include answer correctness, citation correctness, retrieval recall, latency including code generation, token cost, tool calls, rerank pairs, invalid code rate, and reflection trigger precision.",
        ["eval-sac-policy", "roadmap-rovo-sac"],
        ["policy_lookup", "aggregate", "answer_synthesis"],
        hard_negatives=["runbook-regulated-upgrade", "decoy-guide-018"],
        answer_fields={"systems": ["fixed enriched retrieval", "multi-turn tool calling", "one-shot generated code", "reflective generated code"]},
        ideal_routes=[{"query": "Search-as-Code eval compare fixed enriched tool calling one-shot reflective", "mode": "hybrid", "top_k": 10}],
    )
    task(
        "sac-025",
        "test",
        "negative_evidence",
        "hard",
        "Should BluePeak Insurance be included in the SAML connector emergency rollout?",
        "No. BluePeak runs AtlasSearch, but its blocker is the rerank cache issue not SAML connector: CVE-2026-4520 / SEC-1899. The SAML connector emergency rollout is CVE-2026-4102 / SEC-1842 and applies to Northwind Health and Riverline Logistics.",
        ["acct-bluepeak", "esc-bluepeak", "adv-atlas-rerank-4520", "adv-atlas-saml-4102", "ticket-sec-1842"],
        ["negative_evidence_check", "exact_identifier_lookup", "join", "reflection"],
        hard_negatives=["acct-northwind", "acct-riverline"],
        answer_fields={"include": False, "reason": "rerank cache issue not SAML connector"},
        ideal_routes=[
            {"query": "BluePeak Insurance SAML connector SEC-1842", "mode": "hybrid", "top_k": 12},
            {"query": "BluePeak SEC-1899 rerank cache", "mode": "bm25", "top_k": 12},
        ],
        should_reflect=True,
    )
    task(
        "sac-026",
        "dev",
        "budget_control",
        "medium",
        "Which release should not be used for Aster Bank even though it is close to the right version?",
        "Meridian Sync 2.7.4 should not be used. It changed export progress logging but did not fix CVE-2026-2899 or EXPORT-LAT-77. Aster needs 2.7.5.",
        ["acct-aster", "rel-meridian-2-7-4", "rel-meridian-2-7-5"],
        ["exact_version_compare", "negative_evidence_check", "bm25_exact"],
        hard_negatives=["decoy-rel-meridian-sync-2-8-1-01", "decoy-ticket-sec-1341"],
        answer_fields={"reject_version": "2.7.4", "accept_version": "2.7.5"},
        ideal_routes=[{"query": "Aster Bank Meridian Sync 2.7.4 2.7.5 EXPORT-LAT-77", "mode": "bm25", "top_k": 12}],
    )
    task(
        "sac-027",
        "test",
        "wide_fanout",
        "hard",
        "Across all red-risk accounts, which technical owners have more than one renewal blocker assigned?",
        "Mina Patel appears on Northwind Health and Riverline Logistics; Jon Bell appears on Aster Bank and Riverline Logistics; Priya Rao appears on HelioGrid Energy only. Owners with more than one red-risk blocker are Mina Patel and Jon Bell.",
        ["acct-northwind", "acct-aster", "acct-heliogrid", "acct-riverline", "esc-northwind", "esc-aster", "esc-riverline"],
        wide_ops,
        hard_negatives=["acct-bluepeak", "acct-contoso", "acct-urbannest"],
        answer_fields={"owners": ["Mina Patel", "Jon Bell"], "condition": "more than one red-risk blocker"},
        ideal_routes=[{"query": "red risk account technical owner renewal blocker", "mode": "hybrid", "top_k": 30}],
    )
    task(
        "sac-028",
        "test",
        "multi_hop",
        "hard",
        "A regulated customer asks for cache namespace proof. Which customer is most likely asking, what release gives the evidence, and what feature should be cited?",
        "QuartzBio Labs is a regulated life sciences customer asking for rerank cache namespace proof. AtlasSearch 4.9.0 provides Evidence Ledger and tenant-scoped rerank cache.",
        ["acct-quartzbio", "esc-quartzbio", "rel-atlas-4-9-0", "adv-atlas-rerank-4520", "runbook-regulated-upgrade"],
        ["entity_linking", "semantic_search", "join", "multi_hop_reasoning", "rerank"],
        hard_negatives=["acct-bluepeak", "rel-atlas-4-8-2", "adv-atlas-saml-4102"],
        answer_fields={"customer": "QuartzBio Labs", "release": "AtlasSearch 4.9.0", "feature": "Evidence Ledger"},
        ideal_routes=[
            {"query": "regulated cache namespace proof Evidence Ledger", "mode": "dense", "top_k": 20},
            {"query": "QuartzBio Labs rerank cache namespace", "mode": "bm25", "top_k": 15},
        ],
    )
    task(
        "sac-029",
        "train",
        "multi_hop",
        "medium",
        "Which product release both fixed a security issue and added a customer-facing evidence artifact?",
        "AtlasSearch 4.9.0 fixed CVE-2026-4520 and added Evidence Ledger, which is a customer-facing evidence artifact.",
        ["rel-atlas-4-9-0", "adv-atlas-rerank-4520", "acct-bluepeak", "acct-quartzbio"],
        ["semantic_search", "join", "rerank"],
        hard_negatives=["rel-atlas-4-8-2", "rel-rovo-5-3-0", "decoy-rel-atlassearch-4-9-2-02"],
        answer_fields={"release": "AtlasSearch 4.9.0", "feature": "Evidence Ledger", "cve": "CVE-2026-4520"},
        ideal_routes=[{"query": "release fixed CVE added Evidence Ledger", "mode": "hybrid", "top_k": 15}],
    )
    task(
        "sac-030",
        "test",
        "tool_calling_vs_codegen",
        "hard",
        "Which customers have blockers that require exact identifier matching, and what identifiers should the generated code preserve?",
        "Exact identifiers to preserve include ticket IDs and CVEs: Northwind/Riverline SEC-1842 and CVE-2026-4102; Aster/Riverline SEC-1775, CVE-2026-2899, EXPORT-LAT-77; Contoso/UrbanNest SEC-1811 and CVE-2026-3771; BluePeak/QuartzBio SEC-1899 and CVE-2026-4520; HelioGrid/Greenhouse SEC-1690 and CVE-2026-1984; NovaFoods SEC-1604 and CVE-2026-1440.",
        ["ticket-sec-1842", "ticket-sec-1775", "ticket-sec-1811", "ticket-sec-1899", "ticket-sec-1690", "ticket-sec-1604", "acct-northwind", "acct-riverline", "acct-aster", "acct-contoso", "acct-bluepeak", "acct-heliogrid", "acct-novafoods"],
        ["fanout_search", "bm25_exact", "aggregate", "budget_control"],
        hard_negatives=["decoy-ticket-sec-1201", "decoy-ticket-sec-1341", "decoy-ticket-sec-1481", "decoy-ticket-sec-1621"],
        answer_fields={"identifier_types": ["ticket", "CVE", "EXPORT-LAT-77"]},
        ideal_routes=[
            {"query": "SEC CVE blocker customer exact identifier", "mode": "bm25", "top_k": 50},
            {"query": "customer blocker issue ticket CVE", "mode": "hybrid", "top_k": 50},
        ],
    )
    task(
        "sac-031",
        "dev",
        "negative_evidence",
        "hard",
        "Can we claim that AtlasSearch 4.8.1 remediates Northwind's SAML blocker?",
        "No. AtlasSearch 4.8.1 did not fix CVE-2026-4102. Northwind's SAML blocker requires AtlasSearch 4.8.2.",
        ["acct-northwind", "rel-atlas-4-8-1", "rel-atlas-4-8-2", "adv-atlas-saml-4102"],
        ["exact_version_compare", "negative_evidence_check", "reflection"],
        hard_negatives=["adv-atlas-rerank-4520", "rel-atlas-4-9-0"],
        answer_fields={"claim": False, "wrong_version": "4.8.1", "right_version": "4.8.2"},
        ideal_routes=[{"query": "AtlasSearch 4.8.1 4.8.2 CVE-2026-4102 Northwind", "mode": "bm25", "top_k": 12}],
        should_reflect=True,
    )
    task(
        "sac-032",
        "test",
        "comparative_analysis",
        "hard",
        "Compare Northwind Health and Riverline Logistics: which one has a single AtlasSearch blocker and which one has two product blockers?",
        "Northwind Health has a single AtlasSearch SAML blocker tied to CVE-2026-4102 / SEC-1842. Riverline Logistics has two product blockers: AtlasSearch CVE-2026-4102 / SEC-1842 and Meridian Sync CVE-2026-2899 / SEC-1775.",
        ["acct-northwind", "esc-northwind", "acct-riverline", "esc-riverline", "adv-atlas-saml-4102", "adv-meridian-path-2899"],
        ["compare_entities", "join", "aggregate", "bm25_exact"],
        hard_negatives=["acct-aster", "acct-bluepeak", "acct-quartzbio"],
        answer_fields={"single_blocker": "Northwind Health", "two_blockers": "Riverline Logistics"},
        ideal_routes=[
            {"query": "Northwind Riverline blockers AtlasSearch Meridian Sync", "mode": "hybrid", "top_k": 20},
            {"query": "SEC-1842 SEC-1775", "mode": "bm25", "top_k": 20},
        ],
    )
    task(
        "sac-033",
        "test",
        "wide_fanout",
        "hard",
        "Which customers should be excluded from a June critical-patch war room, and why?",
        "Exclude Contoso Retail and UrbanNest because CVE-2026-3771 is high but not critical and renewals are not before July 1; exclude BluePeak Insurance and QuartzBio Labs because CVE-2026-4520 is high but not critical; exclude NovaFoods because its Compass issue is medium; exclude Greenhouse University because the critical ForgeDeploy issue exists but renewal is in August rather than June.",
        ["acct-contoso", "acct-urbannest", "acct-bluepeak", "acct-quartzbio", "acct-novafoods", "acct-greenhouse", "adv-beacon-oauth-3771", "adv-atlas-rerank-4520", "adv-compass-csv-1440", "adv-forge-ssrf-1984"],
        ["negative_filter", "metadata_filter", "aggregate", "join"],
        hard_negatives=["acct-northwind", "acct-aster", "acct-heliogrid", "acct-riverline"],
        answer_fields={"exclude_customers": ["Contoso Retail", "UrbanNest", "BluePeak Insurance", "QuartzBio Labs", "NovaFoods", "Greenhouse University"]},
        ideal_routes=[{"query": "exclude June critical patch war room high medium August renewal", "mode": "hybrid", "top_k": 35}],
        should_reflect=True,
    )
    task(
        "sac-034",
        "train",
        "release_fix_mapping",
        "medium",
        "Which release should be cited for reduced agent trace token volume in the Search-as-Code pilot?",
        "Rovo Chat 5.3.0 should be cited. It includes Search-as-Code experimental mode and tool trace compaction, reducing agent trace token volume by 31 percent in pilot.",
        ["rel-rovo-5-3-0", "roadmap-rovo-sac"],
        ["bm25_exact", "policy_lookup"],
        hard_negatives=["decoy-rel-rovo-chat-5-8-1-01", "eval-sac-policy"],
        answer_fields={"release": "Rovo Chat 5.3.0", "metric": "31 percent"},
        ideal_routes=[{"query": "Rovo Chat 5.3.0 Search-as-Code token volume 31", "mode": "bm25", "top_k": 8}],
    )
    task(
        "sac-035",
        "test",
        "reflection_required",
        "hard",
        "If generated code finds no ForgeDeploy documents for NovaFoods, should it keep searching or answer with negative evidence?",
        "It should answer with negative evidence after checking the NovaFoods product footprint. NovaFoods has no ForgeDeploy workspace, no AtlasSearch tenant, and no Meridian Sync deployment; only Compass Analytics is active.",
        ["negative-forgedeploy-novafoods", "acct-novafoods"],
        ["negative_evidence_check", "evidence_reflection", "stop_condition"],
        hard_negatives=["adv-forge-ssrf-1984", "acct-heliogrid", "acct-greenhouse"],
        answer_fields={"stop": True, "answer": "negative evidence", "active_product": "Compass Analytics"},
        ideal_routes=[{"query": "NovaFoods product footprint no ForgeDeploy", "mode": "bm25", "top_k": 10}],
        should_reflect=True,
    )
    task(
        "sac-036",
        "test",
        "wide_fanout",
        "hard",
        "Which accounts have the same technical owner for different product blockers, and what does that imply for staffing?",
        "Mina Patel owns AtlasSearch blockers for Northwind Health, Riverline Logistics, BluePeak Insurance, and QuartzBio Labs. This indicates AtlasSearch staffing pressure across both SAML and rerank-cache workstreams. Luis Romero owns Beacon blockers for Contoso Retail and UrbanNest. Priya Rao owns ForgeDeploy blockers for HelioGrid Energy and Greenhouse University.",
        ["acct-northwind", "acct-riverline", "acct-bluepeak", "acct-quartzbio", "acct-contoso", "acct-urbannest", "acct-heliogrid", "acct-greenhouse"],
        ["fanout_search", "group_by_owner", "aggregate", "join"],
        hard_negatives=["acct-aster", "acct-novafoods", "decoy-acct-cedar-health"],
        answer_fields={"owners": ["Mina Patel", "Luis Romero", "Priya Rao"]},
        ideal_routes=[{"query": "technical owner product blockers account brief", "mode": "hybrid", "top_k": 45}],
    )

    attach_cluster_hard_negatives(tasks)
    return tasks


def attach_cluster_hard_negatives(tasks: list[dict]) -> None:
    """Attach same-topic cluster docs as hard negatives for representative tasks."""
    extras = {
        "sac-001": [
            "cluster-atlas-saml-4102-digest-001",
            "cluster-atlas-saml-4102-rollout-002",
            "cluster-atlas-saml-4102-ticket-003",
            "cluster-customer-northwind-renewal-002",
            "cluster-product-atlassearch-advisory-005",
        ],
        "sac-002": [
            "cluster-customer-northwind-risk-005",
            "cluster-customer-aster-forecast-007",
            "cluster-customer-heliogrid-audit-008",
            "cluster-customer-riverline-escalation-003",
            "cluster-enterprise-dashboard-004",
        ],
        "sac-004": [
            "cluster-atlas-saml-4102-release-005",
            "cluster-meridian-path-2899-release-005",
            "cluster-customer-riverline-email-004",
            "cluster-product-meridian-sync-kb-003",
            "cluster-product-atlassearch-kb-003",
        ],
        "sac-005": [
            "cluster-atlas-rerank-4520-digest-001",
            "cluster-atlas-rerank-4520-rollout-002",
            "cluster-atlas-rerank-4520-ticket-003",
            "cluster-product-atlassearch-perf-008",
        ],
        "sac-007": [
            "cluster-enterprise-memo-001",
            "cluster-enterprise-thread-002",
            "cluster-enterprise-dashboard-004",
            "cluster-customer-bluepeak-risk-005",
            "cluster-customer-greenhouse-renewal-002",
        ],
        "sac-009": [
            "cluster-atlas-rerank-4520-release-005",
            "cluster-atlas-rerank-4520-faq-009",
            "cluster-product-atlassearch-runbook-004",
            "cluster-customer-bluepeak-email-004",
            "cluster-customer-quartzbio-audit-008",
        ],
        "sac-011": [
            "cluster-customer-northwind-crm-001",
            "cluster-customer-aster-crm-001",
            "cluster-customer-bluepeak-crm-001",
            "cluster-customer-heliogrid-crm-001",
            "cluster-product-atlassearch-migration-002",
            "cluster-product-meridian-sync-migration-002",
        ],
        "sac-013": [
            "cluster-beacon-oauth-3771-digest-001",
            "cluster-beacon-oauth-3771-release-005",
            "cluster-beacon-oauth-3771-faq-009",
            "cluster-product-beacon-crm-connector-release-001",
            "cluster-customer-contoso-renewal-002",
        ],
        "sac-014": [
            "cluster-atlas-saml-4102-approval-007",
            "cluster-beacon-oauth-3771-approval-007",
            "cluster-atlas-rerank-4520-approval-007",
            "cluster-enterprise-review-003",
            "cluster-enterprise-draft-006",
        ],
        "sac-016": [
            "cluster-enterprise-memo-001",
            "cluster-enterprise-thread-002",
            "cluster-enterprise-review-003",
            "cluster-enterprise-draft-006",
            "cluster-product-rovo-chat-runbook-004",
        ],
        "sac-018": [
            "cluster-forge-ssrf-1984-digest-001",
            "cluster-forge-ssrf-1984-rollout-002",
            "cluster-forge-ssrf-1984-release-005",
            "cluster-customer-heliogrid-escalation-003",
        ],
        "sac-020": [
            "cluster-forge-ssrf-1984-email-006",
            "cluster-forge-ssrf-1984-faq-009",
            "cluster-customer-greenhouse-email-004",
            "cluster-product-forgedeploy-advisory-005",
        ],
        "sac-022": [
            "cluster-atlas-rerank-4520-email-006",
            "cluster-atlas-rerank-4520-dashboard-010",
            "cluster-customer-quartzbio-renewal-002",
            "cluster-product-atlassearch-compat-007",
        ],
        "sac-024": [
            "cluster-enterprise-memo-007",
            "cluster-enterprise-thread-008",
            "cluster-enterprise-review-009",
            "cluster-product-rovo-chat-kb-003",
            "cluster-product-rovo-chat-runbook-004",
        ],
        "sac-025": [
            "cluster-atlas-saml-4102-digest-001",
            "cluster-atlas-rerank-4520-digest-001",
            "cluster-customer-bluepeak-risk-005",
            "cluster-product-atlassearch-release-001",
        ],
        "sac-027": [
            "cluster-customer-northwind-forecast-007",
            "cluster-customer-aster-forecast-007",
            "cluster-customer-riverline-forecast-007",
            "cluster-enterprise-dashboard-010",
        ],
        "sac-028": [
            "cluster-atlas-rerank-4520-faq-009",
            "cluster-customer-quartzbio-audit-008",
            "cluster-customer-bluepeak-audit-008",
            "cluster-product-atlassearch-kb-003",
        ],
        "sac-030": [
            "cluster-atlas-saml-4102-ticket-003",
            "cluster-meridian-path-2899-ticket-003",
            "cluster-forge-ssrf-1984-ticket-003",
            "cluster-beacon-oauth-3771-ticket-003",
            "cluster-atlas-rerank-4520-ticket-003",
            "cluster-compass-csv-1440-ticket-003",
        ],
        "sac-032": [
            "cluster-customer-northwind-escalation-003",
            "cluster-customer-riverline-escalation-003",
            "cluster-atlas-saml-4102-meeting-004",
            "cluster-meridian-path-2899-meeting-004",
        ],
        "sac-033": [
            "cluster-enterprise-memo-001",
            "cluster-enterprise-thread-002",
            "cluster-customer-contoso-risk-005",
            "cluster-customer-urbannest-risk-005",
            "cluster-customer-greenhouse-risk-005",
        ],
        "sac-035": [
            "cluster-forge-ssrf-1984-digest-001",
            "cluster-forge-ssrf-1984-rollout-002",
            "cluster-customer-novafoods-audit-008",
            "cluster-product-forgedeploy-kb-003",
        ],
        "sac-036": [
            "cluster-customer-northwind-crm-001",
            "cluster-customer-riverline-crm-001",
            "cluster-customer-bluepeak-crm-001",
            "cluster-customer-quartzbio-crm-001",
            "cluster-enterprise-dashboard-004",
        ],
    }
    by_id = {task["task_id"]: task for task in tasks}
    for task_id, doc_ids in extras.items():
        task = by_id[task_id]
        evidence = set(task["evidence_doc_ids"])
        existing = set(task["hard_negative_doc_ids"])
        for doc_id in doc_ids:
            if doc_id not in evidence and doc_id not in existing:
                task["hard_negative_doc_ids"].append(doc_id)
                existing.add(doc_id)


def build_manifest(documents: list[dict], tasks: list[dict]) -> dict:
    split_counts = Counter(task["split"] for task in tasks)
    category_counts = Counter(task["category"] for task in tasks)
    doc_type_counts = Counter(doc["metadata"].get("doc_type", "unknown") for doc in documents)
    operation_counts = Counter(op for task in tasks for op in task["required_operations"])
    return {
        "dataset_version": VERSION,
        "description": "Custom Search-as-Code benchmark for codegen, fanout, join, filter, reflection, and budget-control tasks.",
        "documents": len(documents),
        "tasks": len(tasks),
        "splits": dict(sorted(split_counts.items())),
        "categories": dict(sorted(category_counts.items())),
        "document_types": dict(sorted(doc_type_counts.items())),
        "operation_coverage": dict(sorted(operation_counts.items())),
        "files": {
            "corpus": "data/corpus.jsonl",
            "tasks": "data/tasks.jsonl",
            "hard_negatives": "data/hard_negatives.jsonl",
            "quality_report": "data/quality_report.json",
            "beir_corpus": "data/beir/corpus.jsonl",
            "beir_queries": "data/beir/queries.jsonl",
            "beir_qrels": "data/beir/qrels/{train,dev,test}.tsv",
            "beir_hard_negatives": "data/beir/hard_negatives/{train,dev,test}.tsv",
        },
    }


def build_hard_negative_rows(tasks: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for task in tasks:
        for doc_id in task["hard_negative_doc_ids"]:
            rows.append(
                {
                    "task_id": task["task_id"],
                    "split": task["split"],
                    "doc_id": doc_id,
                    "score": 0,
                }
            )
    return rows


def write_beir(documents: list[dict], tasks: list[dict]) -> None:
    write_jsonl(
        BEIR_DIR / "corpus.jsonl",
        [
            {
                "_id": doc["doc_id"],
                "title": doc["title"],
                "text": doc["text"],
                "metadata": doc["metadata"],
            }
            for doc in documents
        ],
    )
    write_jsonl(
        BEIR_DIR / "queries.jsonl",
        [
            {
                "_id": task["task_id"],
                "text": task["query"],
                "metadata": {
                    "category": task["category"],
                    "difficulty": task["difficulty"],
                    "split": task["split"],
                },
            }
            for task in tasks
        ],
    )

    qrels_dir = BEIR_DIR / "qrels"
    hard_negatives_dir = BEIR_DIR / "hard_negatives"
    qrels_dir.mkdir(parents=True, exist_ok=True)
    hard_negatives_dir.mkdir(parents=True, exist_ok=True)
    by_split: dict[str, list[dict]] = defaultdict(list)
    for task in tasks:
        by_split[task["split"]].append(task)
    for split, rows in by_split.items():
        with (qrels_dir / f"{split}.tsv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle, delimiter="\t")
            writer.writerow(["query-id", "corpus-id", "score"])
            for task in rows:
                for doc_id in task["evidence_doc_ids"]:
                    writer.writerow([task["task_id"], doc_id, 2])
        with (hard_negatives_dir / f"{split}.tsv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle, delimiter="\t")
            writer.writerow(["query-id", "corpus-id", "score"])
            for task in rows:
                for doc_id in task["hard_negative_doc_ids"]:
                    writer.writerow([task["task_id"], doc_id, 0])


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def print_summary(documents: list[dict], tasks: list[dict]) -> None:
    manifest = build_manifest(documents, tasks)
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

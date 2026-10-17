"""
Seed data - populates the graph with realistic company data.
Run: python graph/seed_data.py
"""

from __future__ import annotations
from typing import TYPE_CHECKING

from .models import (
    NodeType, RelationshipType,
    Person, Project, System, Document, Decision,
    Meeting, Ticket, Skill, Team, Concept,
)
from .inmemory_context import InMemoryContext

if TYPE_CHECKING:
    from .base import GraphContext


PEOPLE = [
    Person(name="Alice Chen", role="Staff Engineer", team="Platform",
           email="alice.chen@fakemail.dev", skills=["Python", "Redis", "GQL", "Docker"],
           hire_date="2020-03-15"),
    Person(name="Bob Rivera", role="Product Manager", team="Platform",
           email="bob.rivera@fakemail.dev", skills=["roadmapping", "user-research"],
           hire_date="2019-06-01"),
    Person(name="Carol Kim", role="Security Engineer", team="Security",
           email="carol.kim@fakemail.dev", skills=["Python", "threat-modeling", "CI/CD"],
           hire_date="2021-09-22"),
    Person(name="Dave Okafor", role="Frontend Lead", team="Product",
           email="dave.okafor@fakemail.dev", skills=["React", "TypeScript", "UX"],
           hire_date="2018-11-10"),
    Person(name="Eve Martinez", role="DevOps Engineer", team="Platform",
           email="eve.martinez@fakemail.dev", skills=["Kubernetes", "Terraform", "AWS"],
           hire_date="2022-01-18"),
]

TEAMS = [
    Team(name="Platform", description="Core infrastructure and data platform"),
    Team(name="Security", description="Application and platform security"),
    Team(name="Product", description="Product development and UI/UX"),
    Team(name="Data", description="Analytics and ML"),
]

PROJECTS = [
    Project(name="GraphDB Migration", description="Migrate legacy PostgreSQL metadata into FalkorDB knowledge graph",
            status="active", start_date="2025-02-01", end_date=""),
    Project(name="Auth Service", description="Unified authentication and authorization microservice",
            status="active", start_date="2024-10-15", end_date=""),
    Project(name="API Gateway", description="Central API gateway with rate limiting and observability",
            status="completed", start_date="2024-03-01", end_date="2024-08-15"),
    Project(name="Analytics Dashboard", description="Internal analytics dashboard for product metrics",
            status="active", start_date="2025-01-10", end_date=""),
]

SYSTEMS = [
    System(name="FalkorDB", type="database", criticality="high",
           owner="Alice Chen", description="Graph database for knowledge layer"),
    System(name="AuthService", type="service", criticality="high",
           owner="Bob Rivera", description="OAuth2 / OIDC authentication service"),
    System(name="APIGateway", type="service", criticality="medium",
           owner="Eve Martinez", description="Kong-based API gateway"),
    System(name="CI/CD-Pipeline", type="service", criticality="high",
           owner="Carol Kim", description="GitHub Actions pipeline for CI/CD"),
    System(name="Kubernetes", type="orchestrator", criticality="high",
           owner="Eve Martinez", description="EKS cluster running all services"),
]

SKILLS = [
    Skill(name="Python", category="language"),
    Skill(name="React", category="language"),
    Skill(name="TypeScript", category="language"),
    Skill(name="Redis", category="database"),
    Skill(name="GQL", category="query"),
    Skill(name="Docker", category="devops"),
    Skill(name="Kubernetes", category="devops"),
    Skill(name="Terraform", category="devops"),
    Skill(name="AWS", category="cloud"),
    Skill(name="Threat Modeling", category="security"),
    Skill(name="CI/CD", category="devops"),
    Skill(name="Roadmapping", category="product"),
    Skill(name="UX", category="design"),
    Skill(name="User Research", category="product"),
]

DOCUMENTS = [
    Document(title="ADR-001: Choose FalkorDB for Knowledge Graph",
             type="adr", summary="Decision record for adopting FalkorDB as the knowledge layer",
             created_by="Alice Chen", created_date="2025-01-20", url="/docs/adr-001"),
    Document(title="Auth Service API Spec",
             type="spec", summary="OpenAPI spec for the unified auth service",
             created_by="Bob Rivera", created_date="2024-11-05", url="/docs/auth-spec"),
    Document(title="CI/CD Security Guidelines",
             type="doc", summary="Security guidelines for CI/CD pipelines",
             created_by="Carol Kim", created_date="2024-09-12", url="/docs/ci-security"),
    Document(title="Post-Mortem: API Gateway Outage Jan 2024",
             type="postmortem", summary="Post-mortem for the Jan 2024 API gateway outage",
             created_by="Eve Martinez", created_date="2024-02-03", url="/docs/postmortem-jan2024"),
]

DECISIONS = [
    Decision(title="ADR-001: Choose FalkorDB for Knowledge Graph",
             rationale="FalkorDB offers fast traversals on every agent step and supports isolated graphs per tenant",
             date="2025-01-20", status="accepted", outcome="Project started using FalkorDB"),
    Decision(title="Migrate auth to centralized service",
             rationale="Multiple services have duplicated auth logic; consolidation reduces attack surface",
             date="2024-09-01", status="accepted", outcome="Auth service launched"),
    Decision(title="Disable automatic deployment on Fridays",
             rationale="Friday deployments have a 3x higher rollback rate",
             date="2024-03-15", status="accepted", outcome="CI/CD pipeline updated"),
]

MEETINGS = [
    Meeting(title="Q1 Planning: GraphDB Migration",
            date="2025-01-08", agenda="Plan Q1 work for migrating metadata to graph",
            notes="Alice owns the technical design. Bob handles product questions."),
    Meeting(title="Security Review: Auth Service",
            date="2024-10-20", agenda="Review security posture of new auth service",
            notes="Carol raised concerns about token revocation. Follow-up ticket created."),
    Meeting(title="Post-Outage Retro: API Gateway",
            date="2024-02-01", agenda="Investigate root cause of Jan outage",
            notes="Eve presented findings. Decision: add circuit breaker to gateway."),
]

TICKETS = [
    Ticket(title="Implement token revocation endpoint",
           description="Add endpoint for revoking OAuth2 tokens before expiry",
           status="open", priority="high", assignee="Carol Kim",
           created_date="2024-10-25"),
    Ticket(title="Add circuit breaker to API gateway",
           description="Implement circuit breaker pattern in gateway",
           status="resolved", priority="medium", assignee="Eve Martinez",
           created_date="2024-02-05"),
    Ticket(title="Set up graph traversal benchmarks",
           description="Benchmark query performance for common traversal patterns",
           status="open", priority="medium", assignee="Alice Chen",
           created_date="2025-02-15"),
]


def seed(ctx: "GraphContext") -> None:
    """Populate *ctx* with the seed data above."""
    ctx.delete_graph()

    # Teams
    for team in TEAMS:
        ctx.add_node(NodeType.TEAM.value, team.to_node()[1])

    # People + skills + team membership
    for person in PEOPLE:
        label, props = person.to_node()
        nid = ctx.add_node(label, props)

        team_node = ctx.find_node(NodeType.TEAM.value, "name", person.team)
        if team_node:
            ctx.add_relationship(nid, RelationshipType.MEMBER_OF.value, team_node.id)

        for skill_name in person.skills:
            sk = ctx.find_node(NodeType.SKILL.value, "name", skill_name)
            if not sk:
                sk_label, sk_props = Skill(name=skill_name).to_node()
                sk_id = ctx.add_node(sk_label, sk_props)
                sk = ctx.find_node(NodeType.SKILL.value, "name", skill_name)
            if sk:
                ctx.add_relationship(nid, RelationshipType.HAS_SKILL.value, sk.id)

    # Ensure all skills exist
    for skill in SKILLS:
        if not ctx.find_node(NodeType.SKILL.value, "name", skill.name):
            ctx.add_node(NodeType.SKILL.value, skill.to_node()[1])

    # Projects
    for proj in PROJECTS:
        ctx.add_node(NodeType.PROJECT.value, proj.to_node()[1])

    # Systems + owners
    for sys_obj in SYSTEMS:
        sys_label, sys_props = sys_obj.to_node()
        sys_id = ctx.add_node(sys_label, sys_props)
        owner = ctx.find_node(NodeType.PERSON.value, "name", sys_obj.owner)
        if owner:
            ctx.add_relationship(owner.id, RelationshipType.OWNS.value, sys_id)

    # People -> Projects
    assignments = [
        ("Alice Chen", "GraphDB Migration"),
        ("Alice Chen", "Auth Service"),
        ("Bob Rivera", "GraphDB Migration"),
        ("Bob Rivera", "Auth Service"),
        ("Carol Kim", "Auth Service"),
        ("Carol Kim", "CI/CD-Pipeline"),
        ("Dave Okafor", "Analytics Dashboard"),
        ("Eve Martinez", "API Gateway"),
        ("Eve Martinez", "CI/CD-Pipeline"),
    ]
    for person_name, project_name in assignments:
        p = ctx.find_node(NodeType.PERSON.value, "name", person_name)
        pr = ctx.find_node(NodeType.PROJECT.value, "name", project_name)
        if p and pr:
            ctx.add_relationship(p.id, RelationshipType.WORKS_ON.value, pr.id)

    # Project -> System (USES)
    project_systems = [
        ("GraphDB Migration", "FalkorDB"),
        ("Auth Service", "AuthService"),
        ("Auth Service", "CI/CD-Pipeline"),
        ("API Gateway", "Kubernetes"),
        ("Analytics Dashboard", "APIGateway"),
        ("CI/CD-Pipeline", "Kubernetes"),
    ]
    for proj_name, sys_name in project_systems:
        pr = ctx.find_node(NodeType.PROJECT.value, "name", proj_name)
        sy = ctx.find_node(NodeType.SYSTEM.value, "name", sys_name)
        if pr and sy:
            ctx.add_relationship(pr.id, RelationshipType.USES.value, sy.id)

    # System -> System (DEPENDS_ON)
    system_deps = [
        ("APIGateway", "Kubernetes"),
        ("AuthService", "FalkorDB"),
        ("FalkorDB", "Kubernetes"),
        ("CI/CD-Pipeline", "Kubernetes"),
    ]
    for src_sys, tgt_sys in system_deps:
        s = ctx.find_node(NodeType.SYSTEM.value, "name", src_sys)
        t = ctx.find_node(NodeType.SYSTEM.value, "name", tgt_sys)
        if s and t:
            ctx.add_relationship(s.id, RelationshipType.DEPENDS_ON.value, t.id)

    # Documents, Decisions, Meetings, Tickets
    for doc in DOCUMENTS:
        ctx.add_node(NodeType.DOCUMENT.value, doc.to_node()[1])
    for dec in DECISIONS:
        ctx.add_node(NodeType.DECISION.value, dec.to_node()[1])
    for mtg in MEETINGS:
        ctx.add_node(NodeType.MEETING.value, mtg.to_node()[1])
    for tkt in TICKETS:
        ctx.add_node(NodeType.TICKET.value, tkt.to_node()[1])

    # Decision -> Document (BASED_ON)
    dec_doc_links = [
        ("ADR-001: Choose FalkorDB for Knowledge Graph", "ADR-001: Choose FalkorDB for Knowledge Graph"),
        ("Migrate auth to centralized service", "Auth Service API Spec"),
    ]
    for dec_title, doc_title in dec_doc_links:
        d = ctx.find_node(NodeType.DECISION.value, "title", dec_title)
        dg = ctx.find_node(NodeType.DOCUMENT.value, "title", doc_title)
        if d and dg:
            ctx.add_relationship(d.id, RelationshipType.BASED_ON.value, dg.id)

    # Decision -> Meeting (MADE_IN)
    dec_mtg_links = [
        ("ADR-001: Choose FalkorDB for Knowledge Graph", "Q1 Planning: GraphDB Migration"),
        ("Migrate auth to centralized service", "Security Review: Auth Service"),
        ("Disable automatic deployment on Fridays", "Post-Outage Retro: API Gateway"),
    ]
    for dec_title, mtg_title in dec_mtg_links:
        d = ctx.find_node(NodeType.DECISION.value, "title", dec_title)
        m = ctx.find_node(NodeType.MEETING.value, "title", mtg_title)
        if d and m:
            ctx.add_relationship(d.id, RelationshipType.MADE_IN.value, m.id)

    # Person -> Meeting (ATTENDED)
    person_meetings = [
        ("Alice Chen", "Q1 Planning: GraphDB Migration"),
        ("Bob Rivera", "Q1 Planning: GraphDB Migration"),
        ("Carol Kim", "Security Review: Auth Service"),
        ("Eve Martinez", "Post-Outage Retro: API Gateway"),
    ]
    for person_name, mtg_title in person_meetings:
        p = ctx.find_node(NodeType.PERSON.value, "name", person_name)
        m = ctx.find_node(NodeType.MEETING.value, "title", mtg_title)
        if p and m:
            ctx.add_relationship(p.id, RelationshipType.ATTENDED.value, m.id)

    # Person -> Ticket (RAISED)
    p = ctx.find_node(NodeType.PERSON.value, "name", "Carol Kim")
    t = ctx.find_node(NodeType.TICKET.value, "title", "Implement token revocation endpoint")
    if p and t:
        ctx.add_relationship(p.id, RelationshipType.RAISED.value, t.id)

    # Ticket -> Decision (TRACKS)
    t = ctx.find_node(NodeType.TICKET.value, "title", "Implement token revocation endpoint")
    d = ctx.find_node(NodeType.DECISION.value, "title", "Migrate auth to centralized service")
    if t and d:
        ctx.add_relationship(t.id, RelationshipType.TRACKS.value, d.id)

    # Project -> Decision (HAS_DECISION)
    proj_dec = [
        ("Auth Service", "Migrate auth to centralized service"),
        ("GraphDB Migration", "ADR-001: Choose FalkorDB for Knowledge Graph"),
    ]
    for proj_name, dec_title in proj_dec:
        pr = ctx.find_node(NodeType.PROJECT.value, "name", proj_name)
        d = ctx.find_node(NodeType.DECISION.value, "title", dec_title)
        if pr and d:
            ctx.add_relationship(pr.id, RelationshipType.HAS_DECISION.value, d.id)

    # Person -> Person (RELATED_TO collaboration)
    contacts = [
        ("Alice Chen", "Carol Kim"),
        ("Alice Chen", "Bob Rivera"),
        ("Carol Kim", "Eve Martinez"),
        ("Bob Rivera", "Dave Okafor"),
    ]
    for a, b in contacts:
        na = ctx.find_node(NodeType.PERSON.value, "name", a)
        nb = ctx.find_node(NodeType.PERSON.value, "name", b)
        if na and nb:
            ctx.add_relationship(na.id, RelationshipType.RELATED_TO.value, nb.id)


if __name__ == "__main__":
    ctx = InMemoryContext()
    seed(ctx)
    print(ctx.save_snapshot())
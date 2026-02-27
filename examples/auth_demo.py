"""
Demonstration of swarm-auth integration with swarm-it-api.

Shows the recommended architecture:
1. HeaderIdentityAdapter - trust OAuth2-Proxy headers
2. RBACPolicyAdapter - check authorization
3. VaultCredentialBroker - vend short-lived credentials (mock)
"""

from swarm_auth.adapters.header_identity import HeaderIdentityAdapter
from swarm_auth.adapters.rbac_policy import RBACPolicyAdapter
from swarm_auth.ports.policy_port import Action, Resource, Decision


def main():
    """Demonstrate complete authentication and authorization flow."""

    print("=== Swarm Auth Demo ===\n")

    # Initialize adapters
    identity_adapter = HeaderIdentityAdapter()
    policy_adapter = RBACPolicyAdapter()

    # Scenario 1: Developer accessing OpenAI
    print("Scenario 1: Developer accessing OpenAI Chat")
    print("-" * 50)

    developer_headers = {
        "X-Auth-Request-User": "alice",
        "X-Auth-Request-Email": "alice@example.com",
        "X-Auth-Request-Groups": "developers",
    }

    user = identity_adapter.verify_request(developer_headers)
    print(f"[OK] User extracted: {user.username} (role: {user.role.value})")

    action = Action(verb="generate", provider="openai", resource_type="chat")
    resource = Resource(provider="openai", resource_type="project", identifier="proj-123", attributes={})

    decision = policy_adapter.evaluate(user, action, resource)

    if decision.decision == Decision.ALLOW:
        print(f"[OK] Authorization: ALLOWED")
        print(f"  - Max tokens: {decision.max_tokens}")
        print(f"  - Max cost: ${decision.max_cost}/hour")
        print(f"  - Reason: {decision.reason}")
    else:
        print(f"[DENY] Authorization: DENIED")
        print(f"  - Reason: {decision.reason}")

    print()

    # Scenario 2: Guest accessing OpenAI (limited)
    print("Scenario 2: Guest accessing OpenAI Chat")
    print("-" * 50)

    guest_headers = {
        "X-Auth-Request-User": "guest123",
        "X-Auth-Request-Email": "guest@example.com",
        "X-Auth-Request-Groups": "guest",
    }

    guest = identity_adapter.verify_request(guest_headers)
    print(f"[OK] User extracted: {guest.username} (role: {guest.role.value})")

    decision = policy_adapter.evaluate(guest, action, resource)

    if decision.decision == Decision.ALLOW:
        print(f"[OK] Authorization: ALLOWED")
        print(f"  - Max tokens: {decision.max_tokens} (limited)")
        print(f"  - Max cost: ${decision.max_cost}/hour (limited)")
    else:
        print(f"[DENY] Authorization: DENIED")

    print()

    # Scenario 3: Guest trying to write to S3 (should fail)
    print("Scenario 3: Guest trying to write to AWS S3")
    print("-" * 50)

    s3_action = Action(verb="put", provider="aws", resource_type="s3")
    s3_resource = Resource(provider="aws", resource_type="bucket", identifier="my-bucket", attributes={})

    decision = policy_adapter.evaluate(guest, s3_action, s3_resource)

    if decision.decision == Decision.ALLOW:
        print(f"[OK] Authorization: ALLOWED")
    else:
        print(f"[DENY] Authorization: DENIED (expected)")
        print(f"  - Reason: {decision.reason}")

    print()

    # Scenario 4: Admin accessing audit logs
    print("Scenario 4: Admin accessing audit logs")
    print("-" * 50)

    admin_headers = {
        "X-Auth-Request-User": "admin",
        "X-Auth-Request-Email": "admin@example.com",
        "X-Auth-Request-Groups": "admin",
    }

    admin = identity_adapter.verify_request(admin_headers)
    print(f"[OK] User extracted: {admin.username} (role: {admin.role.value})")

    audit_action = Action(verb="read", provider="aws", resource_type="audit")
    audit_resource = Resource(provider="aws", resource_type="logs", identifier="audit-logs", attributes={})

    decision = policy_adapter.evaluate(admin, audit_action, audit_resource)

    if decision.decision == Decision.ALLOW:
        print(f"[OK] Authorization: ALLOWED")
        print(f"  - Reason: {decision.reason}")
    else:
        print(f"[DENY] Authorization: DENIED")

    print()

    # Scenario 5: Service account accessing OpenAI
    print("Scenario 5: Service account accessing OpenAI")
    print("-" * 50)

    service_headers = {
        "X-Auth-Request-User": "service-bot",
        "X-Auth-Request-Groups": "service",
    }

    service = identity_adapter.verify_request(service_headers)
    print(f"[OK] User extracted: {service.username} (role: {service.role.value})")

    decision = policy_adapter.evaluate(service, action, resource)

    if decision.decision == Decision.ALLOW:
        print(f"[OK] Authorization: ALLOWED")
        print(f"  - Max cost: ${decision.max_cost}/hour")
    else:
        print(f"[DENY] Authorization: DENIED")

    print("\n=== Demo Complete ===")


if __name__ == "__main__":
    main()

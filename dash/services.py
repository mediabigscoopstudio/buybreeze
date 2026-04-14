from .models import Lead, LeadAssignmentHistory, UserProfile


def assign_lead(lead, assigned_by, assigned_to):
    """
    Handles assignment + history tracking
    """

    # Save history
    LeadAssignmentHistory.objects.create(
        lead=lead,
        assigned_from=assigned_by,
        assigned_to=assigned_to,
        assigned_by_role=assigned_by.role
    )

    # Update lead owner
    lead.assigned_to = assigned_to
    lead.save()

    return lead

def can_assign(assigned_by, assigned_to):
    role_map = {
        'admin': 'manager',
        'manager': 'tl',
        'tl': 'employee'
    }

    return role_map.get(assigned_by.role) == assigned_to.role
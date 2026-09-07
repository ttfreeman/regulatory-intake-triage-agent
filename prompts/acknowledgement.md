{%- if route == "DutyOfficer" -%}
Dear {{ reporter_name }},

Thank you for contacting us about this matter (reference {{ record_id }}). Because
of the nature of what you described, this has been escalated immediately to our duty
officer for urgent follow-up. You do not need to take any further action; a member of
our team will be in contact directly.

Regulatory Intake Team
{%- elif route == "RecordsOnly" -%}
Dear {{ reporter_name }},

Thank you for your self-report (reference {{ record_id }}). This has been logged on
the record as required. Based on the details provided, this does not appear to require
further regulatory action, but the record remains available for review.

Regulatory Intake Team
{%- elif route == "FieldInspection" -%}
Dear {{ reporter_name }},

Thank you for bringing this to our attention (reference {{ record_id }}). This has
been assigned to our field inspection queue and will be reviewed within 3 business
days. We will follow up with next steps once an inspection has been completed.

Regulatory Intake Team
{%- elif route == "OperatorLiaison" -%}
Dear {{ reporter_name }},

Thank you for your submission (reference {{ record_id }}). This has been assigned to
our operator liaison team and you can expect a substantive response within 20 business
days.

Regulatory Intake Team
{%- elif route == "IntakeClose" -%}
Dear {{ reporter_name }},

Thank you for contacting us (reference {{ record_id }}). We have logged your message.
No further regulatory action is required at this time; this file is now closed.

Regulatory Intake Team
{%- elif route == "CallbackQueue" -%}
Dear {{ reporter_name }},

Thank you for contacting us (reference {{ record_id }}). We were not able to identify
enough detail (such as a location or the responsible operator) to route this. A member
of our team will attempt to call you back for more information.

Regulatory Intake Team
{%- else -%}
Dear {{ reporter_name }},

Thank you for contacting us (reference {{ record_id }}). Your submission has been
received and logged.

Regulatory Intake Team
{%- endif -%}

# Demo Credentials

These accounts are created/updated automatically by `python scripts/init_db.py`
(and restored by `python scripts/reset_demo_data.py`). They exist purely for
local development and evaluation — the source of truth for every value below
is `scripts/demo_data.py`; update it there, not here, if you change anything.

**Change or disable these before deploying to a real/production environment.**

| Role      | Email                          | Password     | Notes                                   |
|-----------|---------------------------------|--------------|------------------------------------------|
| Admin     | `admin@campushire.ai`          | `Demo@1234`  | Full platform access                     |
| TPO       | `tpo.demo@campushire.ai`       | `Demo@1234`  | Attached to Graphic Era University (GEU) |
| Recruiter | `recruiter.demo@campushire.ai` | `Demo@1234`  | Attached to demo company "Google"        |
| Student   | `student.demo@campushire.ai`   | `Demo@1234`  | Enrolled in GEU, CSE branch, verified    |

A sample placement drive ("Software Engineer Campus Drive (Demo)") is also
seeded for the demo TPO's college so the recruiter/TPO/student dashboards have
data to show immediately after setup.

## Resetting demo data

If demo accounts get into a broken state during local testing (e.g. profile
data edited, password changed, records deleted), restore them without
touching any of your own real data:

```bash
python scripts/reset_demo_data.py
```

This deletes only the specific records defined in `scripts/demo_data.py` and
recreates them — it will never delete unrelated users, colleges, or drives.

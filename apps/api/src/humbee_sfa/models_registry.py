"""Import model modules so SQLAlchemy metadata is fully registered."""

from humbee_sfa.modules.approvals import models as approvals_models
from humbee_sfa.modules.attendance import models as attendance_models
from humbee_sfa.modules.beats import models as beats_models
from humbee_sfa.modules.identity import models as identity_models
from humbee_sfa.modules.leave import models as leave_models
from humbee_sfa.modules.notifications import models as notifications_models
from humbee_sfa.modules.orders import models as orders_models
from humbee_sfa.modules.org import models as org_models
from humbee_sfa.modules.outlets import models as outlets_models
from humbee_sfa.modules.reporting import models as reporting_models
from humbee_sfa.modules.routes import models as routes_models
from humbee_sfa.modules.targets import models as targets_models
from humbee_sfa.platform import models as platform_models

REGISTERED_MODEL_MODULES = (
    approvals_models,
    attendance_models,
    beats_models,
    identity_models,
    leave_models,
    notifications_models,
    org_models,
    orders_models,
    outlets_models,
    reporting_models,
    routes_models,
    targets_models,
    platform_models,
)

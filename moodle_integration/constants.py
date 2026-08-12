SCHEMA_VERSION = 1
MAX_PAYLOAD_SIZE = 1024 * 1024

SUPPORTED_EVENTS = {
    r"core\event\user_created": {
        "action": "created",
        "resources": ("user",),
    },
    r"core\event\user_updated": {
        "action": "updated",
        "resources": ("user",),
    },
    r"core\event\user_deleted": {
        "action": "deleted",
        "resources": ("user",),
    },
    r"core\event\user_enrolment_created": {
        "action": "created",
        "resources": ("enrolment", "user", "course"),
    },
    r"core\event\user_enrolment_deleted": {
        "action": "deleted",
        "resources": ("enrolment", "user", "course"),
    },
}

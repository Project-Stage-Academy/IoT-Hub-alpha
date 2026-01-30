from apps.notifications.models import NotificationTemplate
from .senders import NotificationSender
from .data_structure import AggregateStructure
from apps.events.models import Event
from apps.notifications.tasks import send_notification_with_retries

def action_dispatch(action_config, rule, aggregate):
    action_map = {
        "notification": dispatch_msg,
        "stop_machine": stop_machine,
    }

    action = action_map.get(action_config['type'])
    if action:
        action(action_config, rule, aggregate)
        
    # Write to Events if successful
        
        
def dispatch_msg(action_config, rule, aggregate):
    print(aggregate)
    notif_template = NotificationTemplate.objects.get(id=action_config['template_id'])
        
    template = notif_template.message_template
        
    message = template.format(
        severity=notif_template.get_priority_display(),
        device_name=rule.device.name,
        value=max(aggregate['values']),
        unit=rule.device.device_type.metric_unit
        )
    
    event = event_handler(aggregate, rule, message, notif_template)
    for recipient in notif_template.recipients:
        print(notif_template.id, event.id)
        # send_notification_with_retries.delay(
        #     notif = recipient,
        #     msg = message,
        #     template_id = notif_template.id,
        #     event_id = event.id
        #     )
        
def stop_machine(action_config, rule, aggregate):
    print("Stop machine stub")

def event_handler(aggregate: AggregateStructure, rule, message: str, notif_template):
    new_event = Event(
        timestamp = aggregate['start'],
        severity = notif_template.priority,
        message = message,
        execution_results = {"success": "True"},
        status = "new",
        rule = rule,
        telemetry_snapshot = aggregate
    )
    new_event.save()
    return new_event
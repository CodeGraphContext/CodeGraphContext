"""Canonical example wire.yml text — printed by `cgc wire example`."""

EXAMPLE_WIRE_YML = """\
# .cgc/wire.yml — declared cross-repo wire coupling for MULTI_REPO_LINKS.
#
# Every entry in this file becomes a DECLARED-tier edge in the code graph,
# outranking anything the automatic extractors infer from source. Use it to:
#   * pin producer/consumer relationships across services that share a Kafka topic
#   * link HTTP or gRPC callers to their server implementations across repos
#   * declare that two topic names refer to the same logical channel
#
# The file is read only when config `MULTI_REPO_LINKS` is `true`.
# Validate this file with:   cgc wire validate .cgc/wire.yml

version: 1

topics:
  - system: kafka
    name: group-chat-notifications
    # Fully-qualified symbol names, matching the FQN CGC stores on Function nodes.
    produced_by:
      - groups.impl.KafkaAccessorImpl.publish
    consumed_by:
      - presence_event_processor.RtmGroupChatEventRequestHandler.handle
      - antelope_notification_worker.KafkaMessageConsumer.consume

endpoints:
  - protocol: grpc
    method: GetPresence
    # For gRPC, `path` is the service-qualified FQN of the RPC.
    path: com.ea.eadp.presence.v1.PresenceService/GetPresence
    served_by:
      - presence_frontend_grpc.PresenceServiceGRPC.getPresence
    invoked_by:
      - groups.client.PresenceClient.getPresence

  - protocol: http
    method: POST
    path: /v1/players/{playerId}/invitations
    served_by:
      - groups.rest.InvitationController.create
    invoked_by:
      - presence_frontend_grpc.gateway.InvitationSender.send

aliases:
  topics:
    - canonical: group-chat-notifications
      names:
        - group-chat.notifications
        - group_chat_notifications_v2
  endpoints: []
"""

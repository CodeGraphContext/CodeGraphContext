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
    name: order-events
    # Fully-qualified symbol names, matching the FQN CGC stores on Function nodes.
    produced_by:
      - orders.impl.KafkaPublisherImpl.publish
    consumed_by:
      - event_processor.OrderEventHandler.handle
      - notification_worker.KafkaMessageConsumer.consume

endpoints:
  - protocol: grpc
    method: GetStatus
    # For gRPC, `path` is the service-qualified FQN of the RPC.
    path: com.example.status.v1.StatusService/GetStatus
    served_by:
      - status_gateway.StatusServiceGRPC.getStatus
    invoked_by:
      - orders.client.StatusClient.getStatus

  - protocol: http
    method: POST
    path: /v1/users/{userId}/orders
    served_by:
      - orders.rest.OrderController.create
    invoked_by:
      - status_gateway.gateway.OrderEventSender.send

aliases:
  topics:
    - canonical: order-events
      names:
        - order.events
        - order_events_v2
  endpoints: []
"""

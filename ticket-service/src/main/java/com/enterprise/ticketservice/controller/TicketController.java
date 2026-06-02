package com.enterprise.ticketservice.controller;

import com.enterprise.ticketservice.model.AgentResponse;
import com.enterprise.ticketservice.model.Ticket;
import com.enterprise.ticketservice.service.TicketOrchestrationService;
import jakarta.validation.Valid;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/api/v1/tickets")
public class TicketController {

    private static final Logger log = LoggerFactory.getLogger(TicketController.class);

    private final TicketOrchestrationService orchestrationService;

    public TicketController(TicketOrchestrationService orchestrationService) {
        this.orchestrationService = orchestrationService;
    }

    @PostMapping("/resolve")
    public ResponseEntity<AgentResponse> resolveTicket(@Valid @RequestBody Ticket ticket) {
        log.info("POST /api/v1/tickets/resolve  ticketId={}", ticket.ticketId());
        AgentResponse response = orchestrationService.resolve(ticket);
        return ResponseEntity.ok(response);
    }

    @GetMapping("/{ticketId}/status")
    public ResponseEntity<Map<String, Object>> getTicketStatus(@PathVariable String ticketId) {
        log.info("GET /api/v1/tickets/{}/status", ticketId);
        return ResponseEntity.ok(Map.of(
                "ticketId", ticketId,
                "status", "in_progress",
                "message", "Ticket is being processed by the AI agent.",
                "estimatedResolutionMinutes", 15
        ));
    }
}

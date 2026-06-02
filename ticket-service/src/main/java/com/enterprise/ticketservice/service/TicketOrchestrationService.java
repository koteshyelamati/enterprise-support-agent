package com.enterprise.ticketservice.service;

import com.enterprise.ticketservice.model.AgentResponse;
import com.enterprise.ticketservice.model.Ticket;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientResponseException;

import java.time.Duration;
import java.util.Map;

@Service
public class TicketOrchestrationService {

    private static final Logger log = LoggerFactory.getLogger(TicketOrchestrationService.class);

    private final WebClient webClient;

    @Value("${agent.core.url}")
    private String agentCoreUrl;

    @Value("${agent.core.timeout-seconds:60}")
    private int timeoutSeconds;

    public TicketOrchestrationService(WebClient webClient) {
        this.webClient = webClient;
    }

    public AgentResponse resolve(Ticket ticket) {
        log.info("Sending ticket {} to agent-core at {}", ticket.ticketId(), agentCoreUrl);

        Map<String, String> payload = Map.of(
                "ticket_id", ticket.ticketId(),
                "description", ticket.description()
        );

        return webClient.post()
                .uri(agentCoreUrl + "/agent/resolve")
                .bodyValue(payload)
                .retrieve()
                .bodyToMono(AgentResponse.class)
                .timeout(Duration.ofSeconds(timeoutSeconds))
                .onErrorMap(
                        WebClientResponseException.class,
                        ex -> {
                            log.error("agent-core returned HTTP {}: {}", ex.getStatusCode(), ex.getResponseBodyAsString());
                            return new AgentCoreUnavailableException("agent-core error: " + ex.getStatusCode(), ex);
                        }
                )
                .onErrorMap(
                        ex -> !(ex instanceof AgentCoreUnavailableException),
                        ex -> {
                            log.error("Failed to reach agent-core: {}", ex.getMessage());
                            return new AgentCoreUnavailableException("agent-core is unavailable: " + ex.getMessage(), ex);
                        }
                )
                .block();
    }

    public static class AgentCoreUnavailableException extends RuntimeException {
        public AgentCoreUnavailableException(String message, Throwable cause) {
            super(message, cause);
        }
    }
}

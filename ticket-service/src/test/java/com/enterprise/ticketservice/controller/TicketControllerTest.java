package com.enterprise.ticketservice.controller;

import com.enterprise.ticketservice.model.AgentResponse;
import com.enterprise.ticketservice.model.Ticket;
import com.enterprise.ticketservice.service.TicketOrchestrationService;
import com.enterprise.ticketservice.service.TicketOrchestrationService.AgentCoreUnavailableException;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.MediaType;
import org.springframework.security.test.context.support.WithMockUser;
import org.springframework.test.web.servlet.MockMvc;

import java.util.List;
import java.util.Map;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.csrf;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(TicketController.class)
class TicketControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @MockBean
    private TicketOrchestrationService orchestrationService;

    @Test
    @WithMockUser
    void resolveTicket_validRequest_returns200() throws Exception {
        AgentResponse mockResponse = new AgentResponse(
                "TKT-001", "Cannot reset my password", "medium", "account",
                "Please use the self-service portal at portal.internal/reset.",
                false, 0,
                List.of("analyze_ticket", "query_vector_db", "resolve_ticket"),
                List.of(Map.of("node", "analyze_ticket", "output", Map.of("severity", "medium")))
        );
        when(orchestrationService.resolve(any())).thenReturn(mockResponse);

        Ticket request = new Ticket("TKT-001", "Cannot reset my password, the link expired.", "medium");

        mockMvc.perform(post("/api/v1/tickets/resolve")
                        .with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.ticket_id").value("TKT-001"))
                .andExpect(jsonPath("$.severity").value("medium"))
                .andExpect(jsonPath("$.escalated").value(false))
                .andExpect(jsonPath("$.resolution").isNotEmpty());
    }

    @Test
    @WithMockUser
    void resolveTicket_blankTicketId_returns400() throws Exception {
        String badJson = "{\"ticketId\": \"\", \"description\": \"Cannot reset my password\", \"priority\": \"low\"}";
        mockMvc.perform(post("/api/v1/tickets/resolve")
                        .with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(badJson))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.title").value("Invalid Request"));
    }

    @Test
    @WithMockUser
    void resolveTicket_descriptionTooShort_returns400() throws Exception {
        Ticket request = new Ticket("TKT-002", "short", null);
        mockMvc.perform(post("/api/v1/tickets/resolve")
                        .with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isBadRequest());
    }

    @Test
    void resolveTicket_unauthenticated_returns401() throws Exception {
        Ticket request = new Ticket("TKT-003", "Cannot reset my password, the link expired.", null);
        mockMvc.perform(post("/api/v1/tickets/resolve")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isUnauthorized());
    }

    @Test
    @WithMockUser
    void resolveTicket_agentCoreDown_returns503() throws Exception {
        when(orchestrationService.resolve(any()))
                .thenThrow(new AgentCoreUnavailableException("Connection refused", null));
        Ticket request = new Ticket("TKT-004", "VPN is not connecting from home office.", null);
        mockMvc.perform(post("/api/v1/tickets/resolve")
                        .with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isServiceUnavailable())
                .andExpect(jsonPath("$.title").value("Agent Service Unavailable"));
    }

    @Test
    @WithMockUser
    void getTicketStatus_validId_returns200() throws Exception {
        mockMvc.perform(get("/api/v1/tickets/TKT-001/status"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.ticketId").value("TKT-001"))
                .andExpect(jsonPath("$.status").isNotEmpty())
                .andExpect(jsonPath("$.estimatedResolutionMinutes").isNumber());
    }

    @Test
    void getTicketStatus_unauthenticated_returns401() throws Exception {
        mockMvc.perform(get("/api/v1/tickets/TKT-001/status"))
                .andExpect(status().isUnauthorized());
    }
}

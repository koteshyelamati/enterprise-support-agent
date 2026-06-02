package com.enterprise.ticketservice.model;

import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.List;
import java.util.Map;

/**
 * Response model returned by agent-core and forwarded to API clients.
 * Jackson @JsonProperty maps snake_case JSON fields from agent-core to
 * camelCase Java field names and vice versa.
 */
public record AgentResponse(

        @JsonProperty("ticket_id")
        String ticketId,

        @JsonProperty("description")
        String description,

        @JsonProperty("severity")
        String severity,

        @JsonProperty("category")
        String category,

        @JsonProperty("resolution")
        String resolution,

        @JsonProperty("escalated")
        boolean escalated,

        @JsonProperty("error_count")
        int errorCount,

        @JsonProperty("tool_calls")
        List<String> toolCalls,

        @JsonProperty("history")
        List<Map<String, Object>> history
) {
}

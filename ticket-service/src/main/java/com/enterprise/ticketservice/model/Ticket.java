package com.enterprise.ticketservice.model;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public record Ticket(

        @NotBlank(message = "ticketId must not be blank")
        @Size(min = 1, max = 64, message = "ticketId must be 1-64 characters")
        String ticketId,

        @NotBlank(message = "description must not be blank")
        @Size(min = 10, max = 4096, message = "description must be 10-4096 characters")
        String description,

        String priority
) {
}

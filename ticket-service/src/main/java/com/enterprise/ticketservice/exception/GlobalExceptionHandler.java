package com.enterprise.ticketservice.exception;

import com.enterprise.ticketservice.service.TicketOrchestrationService.AgentCoreUnavailableException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.ProblemDetail;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import java.net.URI;
import java.time.Instant;
import java.util.stream.Collectors;

@RestControllerAdvice
public class GlobalExceptionHandler {

    private static final Logger log = LoggerFactory.getLogger(GlobalExceptionHandler.class);
    private static final String ERROR_BASE_URI = "https://errors.enterprise.example.com/";

    @ExceptionHandler(AgentCoreUnavailableException.class)
    public ProblemDetail handleAgentCoreUnavailable(AgentCoreUnavailableException ex) {
        log.error("agent-core unavailable: {}", ex.getMessage());
        ProblemDetail problem = ProblemDetail.forStatusAndDetail(
                HttpStatus.SERVICE_UNAVAILABLE,
                "The AI agent service is temporarily unavailable. Please retry shortly."
        );
        problem.setTitle("Agent Service Unavailable");
        problem.setType(URI.create(ERROR_BASE_URI + "agent-unavailable"));
        problem.setProperty("timestamp", Instant.now().toString());
        return problem;
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ProblemDetail handleValidation(MethodArgumentNotValidException ex) {
        String errors = ex.getBindingResult().getFieldErrors().stream()
                .map(fe -> fe.getField() + ": " + fe.getDefaultMessage())
                .collect(Collectors.joining("; "));
        log.warn("Validation failure: {}", errors);
        ProblemDetail problem = ProblemDetail.forStatusAndDetail(HttpStatus.BAD_REQUEST,
                "Validation failed: " + errors);
        problem.setTitle("Invalid Request");
        problem.setType(URI.create(ERROR_BASE_URI + "validation-error"));
        problem.setProperty("timestamp", Instant.now().toString());
        return problem;
    }

    @ExceptionHandler(Exception.class)
    public ProblemDetail handleGeneric(Exception ex) {
        log.error("Unexpected error: {}", ex.getMessage(), ex);
        ProblemDetail problem = ProblemDetail.forStatusAndDetail(
                HttpStatus.INTERNAL_SERVER_ERROR, "An unexpected error occurred. Please contact support.");
        problem.setTitle("Internal Server Error");
        problem.setType(URI.create(ERROR_BASE_URI + "internal-error"));
        problem.setProperty("timestamp", Instant.now().toString());
        return problem;
    }
}

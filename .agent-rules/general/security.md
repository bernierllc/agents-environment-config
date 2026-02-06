# Security Rules

## Security Standards

### Authentication and Authorization
- **MCP Servers**: If project has APIs, install MCP server for those APIs
- **Security Requirements**: MCP server MUST respect authorization and authentication
- **Environment Restrictions**: If cannot respect auth, MUST only run in dev environments
- **API Security**: Proper authentication for all external APIs

### Data Protection
- **Sensitive Data**: Never commit sensitive data to version control
- **Environment Variables**: Use environment variables for secrets
- **Database Security**: Secure database connections and queries
- **Input Validation**: Validate all user inputs

## Security Implementation

### API Security
- **Authentication**: Implement proper authentication mechanisms
- **Authorization**: Check permissions for all operations
- **Rate Limiting**: Implement rate limiting for API endpoints
- **Input Sanitization**: Sanitize all inputs to prevent injection attacks

### Database Security
- **Connection Security**: Use encrypted connections
- **Query Security**: Use parameterized queries
- **Access Control**: Implement proper database access controls
- **Audit Logging**: Log security-relevant database operations

### Environment Security
- **Development vs Production**: Separate security configurations
- **Secret Management**: Use secure secret management systems
- **Network Security**: Implement proper network security measures
- **Monitoring**: Monitor for security incidents

## Security Best Practices

### Code Security
- **Secure Coding**: Follow secure coding practices
- **Dependency Management**: Keep dependencies updated and secure
- **Error Handling**: Don't expose sensitive information in errors
- **Logging**: Log security events appropriately

### Infrastructure Security
- **Server Security**: Secure server configurations
- **Network Security**: Implement proper network security
- **Backup Security**: Secure backup and recovery procedures
- **Incident Response**: Have incident response procedures

## Security Monitoring

### Logging and Monitoring
- **Security Events**: Log all security-relevant events
- **Access Logs**: Monitor access to sensitive resources
- **Error Monitoring**: Monitor for security-related errors
- **Performance Monitoring**: Monitor for unusual patterns

### Incident Response
- **Detection**: Implement security incident detection
- **Response**: Have clear incident response procedures
- **Recovery**: Plan for security incident recovery
- **Learning**: Learn from security incidents

## Security Testing

### Security Testing Requirements
- **Vulnerability Scanning**: Regular vulnerability scans
- **Penetration Testing**: Periodic penetration testing
- **Code Review**: Security-focused code reviews
- **Dependency Scanning**: Scan for vulnerable dependencies

### Testing Procedures
- **Automated Testing**: Include security tests in CI/CD
- **Manual Testing**: Manual security testing procedures
- **Third-Party Testing**: Use external security testing services
- **Compliance Testing**: Test for regulatory compliance

## Security Documentation

### Security Documentation Requirements
- **Security Policies**: Document security policies and procedures
- **Incident Response**: Document incident response procedures
- **Security Architecture**: Document security architecture decisions
- **Compliance**: Document compliance requirements

### Documentation Standards
- **Security Guidelines**: Clear security guidelines for developers
- **Threat Modeling**: Document threat models and mitigations
- **Security Controls**: Document implemented security controls
- **Risk Assessment**: Document security risk assessments

## References
- **Architecture**: See `architecture.mdc`
- **Development Workflow**: See `development-workflow.mdc`
- **Port Management**: See `port-management.mdc`
- **CLI Tools**: See `project-setup-cli.mdc`
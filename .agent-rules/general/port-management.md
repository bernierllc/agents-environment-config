# Port Management Rules

## Objective
Centralized port management system to prevent conflicts across all projects on this machine.

## Port Management System

### Central Port Registry
- **File**: `~/projects/ports.json`
- **Format**: JSON with project-specific port allocations
- **Updates**: Required before adding new services or changing ports

### Port Allocation Rules

#### Port Registration Requirements
- **MANDATORY**: All projects MUST register ports in `~/projects/ports.json`
- **BEFORE**: Adding new services or changing existing ports
- **VERIFY**: Check for conflicts before committing port changes
- **UPDATE**: Registry immediately after port changes

#### Port Range Allocations
- **System Ports**: 1-1023 (reserved for system)
- **User Ports**: 1024-49151 (available for projects)
- **Dynamic Ports**: 49152-65535 (OS-assigned)
- **Testing Range**: 5000-5999 (test containers)
- **Development Range**: 3000-3999 (dev servers)
- **Database Range**: 5400-5499 (databases)
- **Cache Range**: 6300-6399 (Redis, Memcached)
- **Webhook Range**: 34000-34999 (test webhooks)

#### Port Naming Convention
```json
{
  "service-type": {
    "service-name": {
      "port": 3536,
      "description": "Clear description of service purpose",
      "environment": "production|development|testing",
      "protocol": "http|tcp|udp",
      "required": true|false
    }
  }
}
```

## Port Management Workflow

### Adding New Ports
1. **Check Registry**: Review `~/projects/ports.json` for conflicts
2. **Select Port**: Choose from appropriate range
3. **Update Registry**: Add new port entry
4. **Update Project**: Modify project configuration
5. **Test**: Verify no conflicts
6. **Commit**: Include both registry and project changes

### Changing Existing Ports
1. **Identify Impact**: Check all projects using the port
2. **Update Registry**: Modify port entry
3. **Update All Projects**: Change all references
4. **Test**: Verify all services work
5. **Commit**: Include all changes together

### Resolving Conflicts
1. **Identify Conflicting Projects**: List all affected projects
2. **Choose Resolution**: Reassign ports or coordinate usage
3. **Update Registry**: Reflect resolution
4. **Update Projects**: Modify all affected configurations
5. **Test**: Verify resolution works
6. **Document**: Add conflict resolution notes

## Port Validation Rules

### Pre-commit Validation
- **Check Registry**: Ensure all project ports are registered
- **Verify No Conflicts**: No duplicate port assignments
- **Validate Ranges**: Ports within appropriate ranges
- **Test Availability**: Verify ports are available

### Port Assignment Guidelines
- **Production Services**: Use stable, well-known ports
- **Development Services**: Use 3000-3999 range
- **Test Services**: Use 5000-5999 range
- **Database Services**: Use 5400-5499 range
- **Cache Services**: Use 6300-6399 range
- **Webhook Services**: Use 34000-34999 range

### Environment-Specific Ports
- **Production**: Stable ports, avoid conflicts
- **Development**: Can use dynamic ranges
- **Testing**: Use dedicated test ranges
- **Staging**: Mirror production port structure

## Port Management Tools

### CLI Tool
- **Path**: `/Users/mattbernier/projects/ports/index.js`
- **Setup**: `node index.js setup [project-dir] -t [tech-stack]`
- **Validate**: `node index.js validate`
- **Help**: `node index.js --help`

### Validation Scripts
```bash
# Check if port is available
lsof -i:<port>

# Validate port configuration
bash validate-ports.sh

# Check for conflicts
jq '.projects | keys[]' ~/projects/ports.json
```

## Best Practices

### Documentation
- **Clear Descriptions**: Explain purpose of each port
- **Environment Tags**: Mark production vs development
- **Dependency Notes**: Document port relationships
- **Change History**: Track port changes over time

### Conflict Prevention
- **Range Separation**: Use different ranges for different purposes
- **Project Isolation**: Avoid sharing ports between projects
- **Reserved Ranges**: Keep system ranges reserved
- **Future Planning**: Leave room for expansion

### Testing and Validation
- **Port Availability**: Test before assignment
- **Service Integration**: Verify services work on assigned ports
- **Conflict Detection**: Regular validation of registry
- **Rollback Plan**: Ability to revert port changes

## Emergency Procedures

### Port Conflict Resolution
1. **Immediate**: Stop conflicting services
2. **Identify**: Find all affected projects
3. **Reassign**: Choose new ports for affected services
4. **Update**: Modify all configurations
5. **Test**: Verify resolution works
6. **Document**: Record conflict and resolution

### Port Registry Recovery
1. **Backup**: Restore from version control
2. **Validate**: Check registry integrity
3. **Reconcile**: Align with actual port usage
4. **Update**: Fix any inconsistencies
5. **Test**: Verify all services work

## Checklist

### Before Adding New Service
- [ ] Check `~/projects/ports.json` for conflicts
- [ ] Select appropriate port from correct range
- [ ] Update port registry with new entry
- [ ] Modify project configuration
- [ ] Test port availability
- [ ] Verify service works on assigned port
- [ ] Commit both registry and project changes

### Before Changing Existing Port
- [ ] Identify all projects using the port
- [ ] Update port registry
- [ ] Update all affected project configurations
- [ ] Test all affected services
- [ ] Verify no new conflicts introduced
- [ ] Commit all changes together

### Regular Maintenance
- [ ] Validate port registry format
- [ ] Check for port conflicts
- [ ] Verify all registered ports are in use
- [ ] Clean up unused port entries
- [ ] Update port descriptions as needed
- [ ] Review and optimize port allocations

## References
- **CLI Tool**: See `project-setup-cli.mdc`
- **Architecture**: See `architecture.mdc`
- **Documentation**: See `/docs/port-management.md`
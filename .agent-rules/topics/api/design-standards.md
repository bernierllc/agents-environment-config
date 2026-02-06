# API Standards

## HTTP Status Code Standards

### 4xx Client Errors
- **400 Bad Request** - Invalid request format, missing required fields
- **401 Unauthorized** - Missing or invalid authentication
- **403 Forbidden** - Authenticated but insufficient permissions
- **404 Not Found** - Resource doesn't exist
- **409 Conflict** - Resource state conflict (e.g., duplicate creation)
- **422 Unprocessable Entity** - Valid format but semantic errors

### 5xx Server Errors
- **500 Internal Server Error** - ONLY for unexpected server conditions
- **502 Bad Gateway** - Upstream service failure
- **503 Service Unavailable** - Service temporarily unavailable

### FORBIDDEN Patterns

❌ **NEVER return 500 for:**
- Missing resources (use 404)
- Invalid user input (use 400)
- Authentication failures (use 401/403)
- Resource conflicts (use 409)

❌ **NEVER return 404 for:**
- Server errors (use 500)
- Authentication failures (use 401/403)

## Response Format Standards

### Success Responses
```typescript
// ✅ Standard success format
return NextResponse.json({
  success: true,
  data: result,
  message: 'Operation completed successfully'
});
```

### Error Responses
```typescript
// ✅ Standard error format
return NextResponse.json({
  success: false,
  error: 'Human readable error message',
  details: 'Additional context for debugging',
  code: 'ERROR_CODE' // Optional error code
}, { status: appropriateStatus });
```

## Validation Requirements

### Input Validation
- **ALWAYS** validate required fields
- **ALWAYS** validate data types
- **ALWAYS** validate business rules
- **ALWAYS** return 400 for validation failures

### Resource Existence
- **ALWAYS** check if resources exist before processing
- **ALWAYS** return 404 for missing resources
- **NEVER** let missing resources cause 500 errors

### Authentication & Authorization
- **ALWAYS** check authentication first
- **ALWAYS** check permissions before processing
- **ALWAYS** return 401/403 for auth failures

## API Request Flow

### Next.js API Routes
1. React → Next.js API Route
2. Next.js API → Python FastAPI (if applicable)
3. Authentication via `X-API-Key` and `X-Admin-API-Key`

### Client Usage
- Use domain-specific builders and fetch functions
- Use shared API client utility for all API calls
- Follow guidelines in project-specific API documentation

## Error Handling Patterns

### Proper Error Handling
```typescript
// ✅ CORRECT - Check existence first
const resource = await service.getResource(id);
if (!resource) {
  return NextResponse.json({ error: 'Resource not found' }, { status: 404 });
}

// ✅ CORRECT - Specific error messages
return NextResponse.json({ 
  error: 'Project not found',
  details: `No project exists with ID: ${projectId}`
}, { status: 404 });

// ❌ WRONG - Generic error messages
return NextResponse.json({ error: 'Something went wrong' }, { status: 500 });
```

## API Client Usage in UI Components

### Use Shared API Client
```typescript
// ✅ CORRECT - Use shared client
import { createUIApiClient, ApiError } from '@/lib/api-client';

const apiClient = createUIApiClient({ authToken });

// ❌ INCORRECT - Don't use fetch directly
const response = await fetch('/api/opportunities');
```

### Error Handling in Components
```typescript
try {
  const response = await apiClient.post('/opportunities', data);
  // Handle success
} catch (err) {
  const apiError = err as ApiError;
  
  if (apiError.status === 400) {
    setError('Invalid data provided');
  } else if (apiError.status === 401) {
    setError('Please log in to continue');
  } else if (apiError.status >= 500) {
    setError('Server error. Please try again later.');
  }
}
```

## Testing Requirements

### API Test Standards
- **ALL** API tests must verify correct status codes
- **ALL** error scenarios must test proper error responses
- **ALL** success scenarios must test proper success responses

```typescript
describe('API Error Handling', () => {
  it('should return 404 for non-existent resource', async () => {
    const response = await request.get('/api/resource/non-existent-id');
    expect(response.status).toBe(404);
    expect(response.body.error).toContain('Resource not found');
  });
});
```

## References
- **Error Handling**: See `general/development-workflow.mdc`
- **TypeScript**: See `languages/typescript/typing-standards.mdc`
- **Testing**: See `frameworks/testing/standards.mdc`
- **Security**: See `general/security.mdc`

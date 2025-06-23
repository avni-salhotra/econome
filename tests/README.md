# Econome Test Suite

Comprehensive testing for the new HTTP-only architecture with Streaming STT V2.

## Overview

This test suite validates the complete architectural migration from WebSocket-based to HTTP-only API, including:

- ✅ **Streaming STT V2** - Real-time speech-to-text with Google Cloud Speech API
- ✅ **HTTP-Only Architecture** - Complete WebSocket removal and HTTP API functionality  
- ✅ **Frontend Audio Pipeline** - Audio processing and streaming capabilities
- ✅ **System Integration** - End-to-end functionality validation
- ✅ **Performance & Security** - Concurrency, error handling, and security validation

## Quick Start

### 1. Install Test Dependencies

```bash
pip install -r tests/requirements-test.txt
```

### 2. Run All Tests

```bash
# Run comprehensive test suite
python3 tests/run_all_tests.py

# Or run individual test suites
python3 -m pytest tests/ -v
```

### 3. Run Quick Architecture Verification

```bash
# Quick verification of new architecture
python3 test_cloud_audio.py
```

## Test Structure

### Core Test Files

| File | Purpose | Coverage |
|------|---------|----------|
| `test_streaming_stt_v2.py` | **Streaming STT V2 functionality** | STT service, audio processing, callbacks |
| `test_http_api_integration.py` | **HTTP API integration** | Endpoints, WebSocket removal, performance |
| `test_e2e_system.py` | **End-to-end system tests** | Full system lifecycle, session management |
| `test_security.py` | **Security validation** | Input validation, error handling |
| `test_cloud_audio.py` | **Architecture verification** | Quick smoke test for deployment |

### Test Categories

#### 🎤 **Streaming STT V2 Tests**
- Service initialization and configuration
- Audio chunk queuing and processing  
- Callback system functionality
- Queue health management
- Session lifecycle (start/stop recording)
- Transcript generation and formatting
- Error handling and resilience

#### 🌐 **HTTP API Tests**
- All endpoint functionality
- WebSocket removal verification
- Frontend streaming functions
- Active conversation management
- Performance and concurrency
- Error handling (404, 500, etc.)

#### 🔧 **Integration Tests**
- Conversation system integration
- Session manager functionality
- Audio processing pipeline
- System status and monitoring
- Memory usage and stability

#### 🔒 **Security Tests**
- Input validation
- Error message sanitization
- Authentication (where applicable)
- Data handling security

## Running Specific Test Categories

### Streaming STT V2 Only
```bash
python3 -m pytest tests/test_streaming_stt_v2.py -v
```

### HTTP API Only
```bash
python3 -m pytest tests/test_http_api_integration.py -v
```

### End-to-End Tests Only  
```bash
python3 -m pytest tests/test_e2e_system.py -v
```

### Performance Tests
```bash
python3 -m pytest tests/test_http_api_integration.py::TestPerformanceAndConcurrency -v
```

## Test Configuration

### Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `TEST_BASE_URL` | API base URL for integration tests | `http://localhost:8080` |
| `TEST_TIMEOUT` | Test timeout in seconds | `120` |
| `LOG_LEVEL` | Logging level for tests | `INFO` |

### Mock Mode

Most tests run in **mock mode** by default, which means:
- ✅ No real GCP credentials required
- ✅ No actual audio hardware needed  
- ✅ Fast execution in CI/CD environments
- ✅ Simulated responses for all external services

## CI/CD Integration

### GitHub Actions

Add to your workflow:

```yaml
- name: Install test dependencies
  run: pip install -r tests/requirements-test.txt

- name: Run comprehensive tests
  run: python3 tests/run_all_tests.py

- name: Run pytest with coverage
  run: python3 -m pytest tests/ --cov=src --cov-report=xml
```

### Docker Testing

```dockerfile
# In your test Dockerfile
COPY tests/requirements-test.txt /app/tests/
RUN pip install -r tests/requirements-test.txt

# Run tests
CMD ["python3", "tests/run_all_tests.py"]
```

## Architecture Validation

The test suite specifically validates the architectural migration:

### ✅ **WebSocket Removal Verified**
- WebSocket endpoints return 404
- `websocket_manager` completely removed
- No WebSocket dependencies in imports
- WebSocket error logs eliminated

### ✅ **HTTP-Only Architecture Confirmed**  
- All API endpoints functional
- Frontend streaming via HTTP
- Session management working
- Error handling robust

### ✅ **Streaming STT V2 Functional**
- Real-time audio processing
- Google Speech API V2 integration
- Streaming configuration correct
- Queue management working

## Troubleshooting

### Common Issues

#### Import Errors
```bash
# Ensure you're in the right directory
cd /path/to/econome
python3 -m pytest tests/
```

#### Missing Dependencies
```bash
pip install -r tests/requirements-test.txt
pip install -r requirements.txt
```

#### GCP Credentials (for real testing)
```bash
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json
```

### Test Failures

#### STT Service Tests Failing
- Check that `speech_agent.py` imports correctly
- Verify mock mode is working
- Ensure audio processing dependencies available

#### HTTP API Tests Failing  
- Verify FastAPI imports work
- Check that web_api.py has no WebSocket references
- Ensure all critical functions preserved

#### Integration Tests Failing
- Check conversation system initialization
- Verify session manager functionality
- Ensure no WebSocket dependencies remain

## Performance Benchmarks

Expected performance for test suite:

| Test Category | Expected Duration | Acceptable Range |
|---------------|------------------|------------------|
| STT V2 Tests | 10-30 seconds | < 60 seconds |
| HTTP API Tests | 15-45 seconds | < 90 seconds |  
| E2E Tests | 5-20 seconds | < 60 seconds |
| **Total Suite** | **30-120 seconds** | **< 300 seconds** |

## Contributing

When adding new tests:

1. **Follow naming convention**: `test_[component]_[functionality].py`
2. **Include docstrings**: Describe what each test validates
3. **Use fixtures**: For setup/teardown and shared data
4. **Mock external services**: Keep tests fast and reliable
5. **Add to test runner**: Update `run_all_tests.py` if needed

## Success Criteria

The test suite passes if:
- ✅ **80%+ of tests pass** (critical threshold)
- ✅ **All architecture verification tests pass**
- ✅ **No WebSocket-related errors**
- ✅ **Core functionality (STT V2, HTTP API) works**
- ✅ **Performance within acceptable ranges**

## Contact

For test-related issues:
- Check this README first
- Review test output logs
- Verify architectural requirements met
- Test in mock mode before real credentials 
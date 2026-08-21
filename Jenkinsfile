def remote = [:]

pipeline {
    agent any

        environment {
            user = credentials('lamaar_user')
            host = credentials('lamaar_host')
            name = credentials('lamaar_host')
            ssh_key = credentials('lamaar_key')
        }

    stages {
        stage('Ssh to connect Lamaar server') {
            steps {
                script {
                    // Set up remote SSH connection parameters
                    remote.allowAnyHosts = true
                    remote.identityFile = ssh_key
                    remote.user = user
                    remote.name = name
                    remote.host = host
                }
            }
        }
        stage('Update code') {
            steps {
                script {
                    try {
                        sshCommand remote: remote, command: """
                            cd /var/www/docs/mcp/aclimate_v3_mcp
                            git checkout main
                            git pull origin main
                            source /home/lamardeployer/miniforge3/etc/profile.d/conda.sh
                            conda activate python3_10
                            uv sync --no-dev
                        """
                    } catch (Exception e) {
                        echo "Git Pull Error: ${e.message}"
                        error("Failed to update code: ${e.message}")
                    }
                }
            }
        }
        stage('Restart MCP service') {
            steps {
                script {
                    try {
                        // Single-quoted Groovy string: no GString interpolation, so shell
                        // variables can be written plainly as $VAR.
                        sshCommand remote: remote, command: '''
                            set -e
                            cd /var/www/docs/mcp/aclimate_v3_mcp/
                            source /home/lamardeployer/miniforge3/etc/profile.d/conda.sh
                            conda activate python3_10

                            # Read the port from the deployed .env instead of hardcoding it,
                            # so killing the old process and probing the new one always
                            # target whatever the service is configured to bind.
                            PORT=$(grep -E '^ACLIMATE_MCP_PORT=' .env | cut -d= -f2 | tr -d '[:space:]')
                            if [ -z "$PORT" ]; then
                                echo "ACLIMATE_MCP_PORT missing from .env"
                                exit 1
                            fi
                            echo "Restarting AClimate MCP on port $PORT"

                            fuser -k "$PORT/tcp" || true
                            sleep 2

                            # setsid + nohup: detach from the SSH session so the service
                            # survives this step's channel closing.
                            setsid nohup uv run aclimate-mcp \
                                > /var/www/docs/mcp/aclimate_v3_mcp/mcp.log 2>&1 < /dev/null &
                        '''
                    } catch (Exception e) {
                        echo "MCP Restart Error: ${e.message}"
                        error("Failed to restart MCP: ${e.message}")
                    }
                }
            }
        }
        stage('Verify MCP service') {
            steps {
                script {
                    try {
                        // Backgrounding the server always returns 0, so the restart stage
                        // cannot tell a running service from one that died on startup.
                        // Poll /health and fail the build if it never answers.
                        sshCommand remote: remote, command: '''
                            set -e
                            cd /var/www/docs/mcp/aclimate_v3_mcp/
                            PORT=$(grep -E '^ACLIMATE_MCP_PORT=' .env | cut -d= -f2 | tr -d '[:space:]')
                            for i in $(seq 1 15); do
                                if curl -fsS "http://127.0.0.1:$PORT/health" > /dev/null; then
                                    echo "MCP healthy on port $PORT"
                                    exit 0
                                fi
                                sleep 2
                            done
                            echo "MCP did not answer /health on port $PORT after 30s. Last log lines:"
                            tail -n 40 /var/www/docs/mcp/aclimate_v3_mcp/mcp.log || true
                            exit 1
                        '''
                    } catch (Exception e) {
                        echo "MCP Health Check Error: ${e.message}"
                        error("MCP did not come up healthy: ${e.message}")
                    }
                }
            }
        }
    }

    post {
        failure {
            script {
                echo "Pipeline failed"
            }
        }
        success {
            script {
                echo 'MCP deployed successfully!'
            }
        }
    }
}

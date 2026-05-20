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
                            source /var/www/docs/mcp/aclimate_v3_mcp/.venv/bin/activate
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
                        sshCommand remote: remote, command: """
                            cd /var/www/docs/mcp/aclimate_v3_mcp/src/aclimate_mcp
                            source /var/www/docs/mcp/aclimate_v3_mcp/.venv/bin/activate
                            fuser -k 8006/tcp || true
                            uv run aclimate-mcp > /var/www/docs/mcp/aclimate_v3_mcp/mcp.log 2>&1 &
                            #uv run uvicorn aclimate_mcp.app.server:app --host 0.0.0.0 --port 8006 > /var/www/docs/mcp/aclimate_v3_mcp/mcp.log 2>&1 &
                        """
                    } catch (Exception e) {
                        echo "API Restart Error: ${e.message}"
                        error("Failed to restart API: ${e.message}")
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

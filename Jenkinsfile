@Library('n9n-jenkins-lib') _

pipeline {
    agent { label 'ansible' }

    options {
        buildDiscarder(logRotator(numToKeepStr: '10', daysToKeepStr: '30'))
    }

    environment {
        // ECR_REPO note: existing eternal-forge image is at <registry>/eternal-forge
        // (no n9n/ prefix), unlike newer apps such as n9n/wagtail-devops. Preserved
        // here to avoid an unrelated image-path migration.
        ECR_REGISTRY = '123456789012.dkr.ecr.us-west-2.amazonaws.com'
        ECR_REPO     = 'eternal-forge'
        AWS_REGION   = 'us-west-2'
        IMAGE_TAG    = "${env.BUILD_NUMBER}"
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Build Docker Image') {
            steps {
                script {
                    sh """
                        docker build -t ${ECR_REGISTRY}/${ECR_REPO}:${IMAGE_TAG} .
                        docker tag ${ECR_REGISTRY}/${ECR_REPO}:${IMAGE_TAG} ${ECR_REGISTRY}/${ECR_REPO}:latest
                    """
                }
            }
        }

        stage('Push to ECR') {
            steps {
                withCredentials([
                    [$class: 'AmazonWebServicesCredentialsBinding', credentialsId: 'ecr-credentials', accessKeyVariable: 'AWS_ACCESS_KEY_ID', secretKeyVariable: 'AWS_SECRET_ACCESS_KEY']
                ]) {
                    script {
                        sh """
                            docker run --rm \
                                -e AWS_ACCESS_KEY_ID=\$AWS_ACCESS_KEY_ID \
                                -e AWS_SECRET_ACCESS_KEY=\$AWS_SECRET_ACCESS_KEY \
                                amazon/aws-cli ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${ECR_REGISTRY}
                            docker push ${ECR_REGISTRY}/${ECR_REPO}:${IMAGE_TAG}
                            docker push ${ECR_REGISTRY}/${ECR_REPO}:latest
                        """
                    }
                }
            }
        }

        stage('Refresh ECR Credentials') {
            steps {
                build job: 'n9n-k8s',
                    parameters: [
                        string(name: 'CLUSTER', value: 'k3s-main'),
                        string(name: 'ACTION', value: 'refresh-ecr'),
                        string(name: 'NAMESPACE', value: 'eternal-system'),
                        booleanParam(name: 'DRY_RUN', value: false)
                    ],
                    wait: true
            }
        }

        stage('Deploy to k3s-main') {
            steps {
                build job: 'n9n-k8s',
                    parameters: [
                        string(name: 'CLUSTER', value: 'k3s-main'),
                        string(name: 'ACTION', value: 'restart'),
                        string(name: 'NAMESPACE', value: 'eternal-system'),
                        string(name: 'APP', value: 'eternal-forge'),
                        booleanParam(name: 'DRY_RUN', value: false)
                    ],
                    wait: true
            }
        }
    }

    post {
        always {
            sh "docker rmi ${ECR_REGISTRY}/${ECR_REPO}:${IMAGE_TAG} || true"
            notifyJenkinsBuild()
        }
        success {
            echo 'Deployment successful! Site available at http://eternal.example.internal'
        }
        failure {
            echo 'Deployment failed. Check logs for details.'
        }
    }
}

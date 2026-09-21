@Library('n9n-jenkins-lib') _

pipeline {
    // agent none, deliberately. The two deploy stages below only wait on
    // n9n-k8s, which runs on label 'ops' -- a different node. Holding an
    // 'ansible' executor while waiting for one is how jenkins-node-1 deadlocked
    // for 18 hours on 2026-09-01: wrappers pinned to one node blocked on
    // downstream builds that needed another. node-2 has only TWO executors, so
    // two concurrent deploys here are enough to wedge it the same way.
    agent none

    options {
        buildDiscarder(logRotator(numToKeepStr: '10', daysToKeepStr: '30'))
    }

    environment {
        // ECR_REPO note: existing eternal-forge image is at <registry>/eternal-forge
        // (no n9n/ prefix), unlike newer apps such as n9n/wagtail-devops. Preserved
        // here to avoid an unrelated image-path migration.
        // Registry and target cluster come from Jenkins global environment
        // variables, so no account id or internal host name lives in this repo.
        ECR_REGISTRY = "${env.AWS_ECR_REGISTRY}"
        DEPLOY_CLUSTER = "${env.APPS_K8S_CLUSTER}"
        ECR_REPO = 'eternal-forge'
        AWS_REGION = 'us-west-2'
        IMAGE_TAG = "${env.BUILD_NUMBER}"
    }

    stages {
        stage('Build and publish') {
            agent { label 'ansible' }

            stages {
                stage('Checkout') {
                    steps {
                        script {
                            if (!env.AWS_ECR_REGISTRY?.trim() || !env.APPS_K8S_CLUSTER?.trim()) {
                                error('Set the AWS_ECR_REGISTRY and APPS_K8S_CLUSTER global environment variables in Jenkins')
                            }
                        }
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
                                        -e AWS_ACCESS_KEY_ID \
                                        -e AWS_SECRET_ACCESS_KEY \
                                        amazon/aws-cli ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${ECR_REGISTRY}
                                    docker push ${ECR_REGISTRY}/${ECR_REPO}:${IMAGE_TAG}
                                    docker push ${ECR_REGISTRY}/${ECR_REPO}:latest
                                """
                            }
                        }
                    }
                }
            }

            // Cleanup belongs to the stage that built the image: it needs the
            // workspace, and this is the only scope guaranteed to be on the
            // agent that created the tags.
            post {
                always {
                    sh "docker rmi ${ECR_REGISTRY}/${ECR_REPO}:${IMAGE_TAG} || true"
                }
            }
        }

        // No agent on these two on purpose -- see the note on `agent none`.
        // `build` needs no workspace, so they run on a flyweight executor.
        stage('Refresh ECR Credentials') {
            steps {
                build job: 'n9n-k8s',
                    parameters: [
                        string(name: 'CLUSTER', value: env.DEPLOY_CLUSTER),
                        string(name: 'ACTION', value: 'refresh-ecr'),
                        string(name: 'NAMESPACE', value: 'eternal-system'),
                        booleanParam(name: 'DRY_RUN', value: false)
                    ],
                    wait: true
            }
        }

        stage('Deploy to n9nweb') {
            steps {
                build job: 'n9n-k8s',
                    parameters: [
                        string(name: 'CLUSTER', value: env.DEPLOY_CLUSTER),
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
            // notifyJenkinsBuild -> notifyNtfy uses sh, which needs a workspace,
            // and this pipeline deliberately has no global agent. Take one
            // briefly here, at the very end, where nothing is queued behind it.
            // Keeping it at pipeline scope (rather than moving it into the build
            // stage) is what makes it report the FINAL result, deploy failures
            // included.
            script {
                node('ansible') {
                    notifyJenkinsBuild()
                }
            }
        }
        success {
            echo 'Deployment successful!'
        }
        failure {
            echo 'Deployment failed. Check logs for details.'
        }
    }
}

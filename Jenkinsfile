pipeline {
    agent any
  
  stages {
        stage('Run Pylint') {
            agent {
                docker {
                    image 'python:3-slim'
		    args '-u 0'
                    reuseNode true
                }
            }
            steps {
		sh 'python3 -m venv venv'
                sh 'pip install --no-cache-dir pylint'
                sh 'pylint --fail-under=0.5 *.py'
            }
        }
        
	stage('Build') {
	   steps {
	       script {
		   docker.build("sharon088/weather_app_image:latest")
	           }
	       }
    	}
	
	stage('Connectivity') {
	   steps {
			script {
				sh 'docker run --rm -d --name web_app_test -p 8000:8000 weather_app_image'
				sh 'python3 connectivity.py'
				sh 'docker stop web_app_test'
			}
	    }
	}
	stage('Push Hub') {
	    steps {
		sh 'docker push sharon088/weather_app_image:latest'
		}
	}

	stage('Deploy') {
    	  steps {
            sshagent(['prod_ssh']) {
              sh '''
                ssh -o StrictHostKeyChecking=no ubuntu@18.194.0.249 "cd /home/ubuntu/jenkins_prod && docker compose pull && docker compose up -d"
                 '''
        		}
   		 }
	}	

}
    post {
        success {
            slackSend(channel: '#succeeded-build', color: 'good', message: "Build #${env.BUILD_NUMBER} succeeded.")
        }
        failure {
            slackSend(channel: '#devops-alerts', color: 'danger', message: "Build #${env.BUILD_NUMBER} failed.")
        }
	always {
            cleanWs()
		}
    }
}


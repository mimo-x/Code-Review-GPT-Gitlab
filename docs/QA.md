# Frequently Asked Questions (FAQ)

This document collects common questions and solutions for the Code Review GPT Gitlab project.

## 📦 Installation & Deployment

!!! question "Q1: What should I do if Docker containers fail to start?"

    !!! tip "Solution"
    
        Please follow these steps to troubleshoot:
    
        1. **Check Docker and Docker Compose versions**
           ```bash
           docker --version
           docker compose version
           ```
           Ensure Docker 20.10+ and Docker Compose v2 are installed.
    
        2. **View container logs**
           ```bash
           docker compose logs backend
           docker compose logs frontend
           ```
    
        3. **Check port occupancy**
           ```bash
           # Check if ports are occupied
           lsof -i :3000  # Frontend port
           lsof -i :8000  # Backend port
           lsof -i :6379  # Redis port
           ```
    
        4. **Rebuild and start**
           ```bash
           docker compose down
           docker compose up -d --build
           ```

!!! question "Q2: How to configure environment variables?"

    !!! info "Configuration Steps"
    
        The project uses `.env` file to manage environment variables:
    
        1. Copy the example file:
           ```bash
           cp .env.example .env
           ```
    
        2. Edit the `.env` file and configure necessary variables:
           - `VITE_API_BASE_URL`: Frontend API base URL
           - `VITE_DEV_PROXY_TARGET`: Development environment proxy target
           - Other necessary configuration items
    
        3. Restart services to apply configuration:
           ```bash
           docker compose restart
           ```

## 🔧 Configuration

!!! question "Q3: How to configure GitLab Webhook?"

    !!! info "Configuration Steps"
    
        Configuration steps:
    
        1. **Get Webhook URL**
           - Format: `http://your-domain.com/api/webhook/gitlab/`
           - Note: URL must end with `/api/webhook/gitlab/`
    
        2. **Configure Webhook in GitLab project**
           - Go to Project Settings → Webhooks
           - Fill in Webhook URL
           - Select trigger events: `Merge Request events`, `Push events`, etc.
           - Save configuration
    
        3. **Enable project review in the system**
           - Log in to the system management interface
           - Go to project list
           - Find the corresponding project and enable code review functionality

## 🚀 Usage

!!! question "Q4: What should I do if code review doesn't trigger automatically?"

    !!! warning "Troubleshooting Steps"
    
        Please check the following:
    
        1. **Check if project review is enabled**
           - Confirm that `review_enabled` status in project list is enabled
           - Confirm that `auto_review_on_mr` option is enabled
    
        2. **Check Webhook configuration**
           - Confirm GitLab Webhook URL is configured correctly
           - Confirm Webhook events are selected correctly
           - Check Webhook logs to confirm if requests are received
    
        3. **Check Webhook event rules**
           - Confirm the project has enabled corresponding Webhook event rules
           - Check `Webhook Logs` to confirm if events are correctly identified
    
        4. **View system logs**
           ```bash
           docker compose logs -f backend
           ```

!!! question "Q5: Code review results are not sending notifications?"

    !!! tip "Troubleshooting Steps"
    
        Troubleshooting steps:
    
        1. **Check notification channel configuration**
           - Confirm notification channel is created and status is active
           - Confirm project is associated with notification channel
           - Check if notification channel configuration information is correct
    
        2. **Check review status**
           - View review records, confirm review status is `completed`
           - Check `notification_sent` field status
           - View error information in `notification_result` field
    
        3. **Test notification channel**
           - Manually test notification channel in management backend
           - Check network connection and API key validity

!!! question "Q6: How to view code review history?"

    !!! info "Viewing Methods"
    
        There are multiple ways to view:
    
        1. **Through frontend interface**
           - Log in to system frontend interface
           - Go to "Review Records" page
           - Can filter by project, time range, etc.
    
        2. **Through management backend**
           - Access `http://localhost:8000/admin/`
           - Go to `Merge Request Reviews` menu
           - View all review records
    
        3. **View detailed logs**
           - Go to "Logs" page to view detailed processing logs
           - Can view logs of each step: Webhook reception, LLM calls, notification sending, etc.

## 🔍 Troubleshooting

!!! question "Q7: Webhook requests are rejected or return 403/401?"

    !!! warning "Possible Causes"
    
        Possible causes:
    
        1. **Check Webhook Secret Token**
           - If Secret Token is configured, ensure the system side also has the same Token configured
    
        2. **Check GitLab Token permissions**
           - Confirm GitLab Token has sufficient permissions to access the project
           - Confirm Token is not expired
    
        3. **Check firewall and network**
           - Confirm server can access GitLab
           - Confirm GitLab can access Webhook URL
    
        4. **View request logs**
           - View detailed request headers and error information in Webhook Logs

!!! question "Q8: System runs slowly or times out?"

    !!! warning "Optimization Suggestions"
    
        Optimization suggestions:
    
        1. **Check resource usage**
           ```bash
           docker stats
           ```
    
        2. **Optimize LLM calls**
           - Use faster models
           - Reduce number of files to review
           - Configure reasonable timeout
    
        3. **Database optimization**
           - Regularly clean up old log records
           - Add indexes to frequently queried fields
    
        4. **Increase resources**
           - Increase container memory limits
           - Use more powerful servers

## 📚 Other Questions

!!! question "Q9: How to upgrade to a new version?"

    !!! tip "Upgrade Steps"
    
        Upgrade steps:
    
        1. **Backup current data**
           ```bash
           # Backup database and configuration
           cp backend/db.sqlite3 backend/db.sqlite3.backup
           cp .env .env.backup
           ```
    
        2. **Pull latest code**
           ```bash
           git pull origin main
           ```
    
        3. **Update dependencies**
           ```bash
           docker compose down
           docker compose build --no-cache
           docker compose up -d
           ```
    
        4. **Execute database migration**
           ```bash
           docker compose exec backend python manage.py migrate
           ```

!!! question "Q10: Which programming languages are supported?"

    !!! info "Language Support"
    
        Theoretically supports all programming languages because:
    
        - The system uses LLM for code review, and LLM itself supports multiple programming languages
        - Does not depend on specific syntax analyzers
        - Review quality depends on LLM model capabilities
    
        !!! tip "Recommendations"
        
            Recommendations:
            - Mainstream languages (Python, JavaScript, Java, Go, etc.) have better review results
            - For special languages, customizing Prompt may be needed for better results

!!! question "Q11: How to contribute code or report issues?"

    !!! success "Welcome Contributions"
    
        Welcome contributions:
    
        1. **Report issues**
           - Submit issues in GitHub Issues
           - Provide detailed error information and reproduction steps
    
        2. **Submit code**
           - Fork the project
           - Create a feature branch
           - Submit Pull Request
    
        3. **Contact maintainers**
           - Email: mixuxin@163.com
           - WeChat: isxuxin

---

!!! tip "💡 Tips"
    
    If none of the above questions solve your problem, please:
    
    1. Check project [GitHub Issues](https://github.com/mimo-x/Code-Review-GPT-Gitlab/issues)
    2. View detailed system logs
    3. Contact project maintainers for help
    
    **Enjoy using!** 🎉


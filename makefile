# Variables
PACKAGE_VERSION ?= latest
ZIP_DIR = version_zip
CURRENT_DATETIME = $(shell date +"%Y%m%d_%H%M%S")

# Ensure proper folder structure for dev and uat
DEV_DIR = $(ZIP_DIR)/dev
UAT_DIR = $(ZIP_DIR)/uat

# Define function names
FUNCTIONS_DEV = "AICorpDesignFA-Dev"
FUNCTIONS_UAT = "AICorpDesignFA-UAT"

# Ensure zip directory structure exists
prepare-dirs:
	@mkdir -p $(DEV_DIR) $(UAT_DIR)
	@echo "Prepared directories for dev and uat."

# Ask the user to select a function
select-function:
	@echo "Select a function to deploy:"
	@echo "1) $(FUNCTIONS_DEV)"
	@echo "2) $(FUNCTIONS_UAT)"
	@read -p "Enter selection (1/2): " choice; \
	if [ "$$choice" = "1" ]; then \
		SELECTED_ENV="dev"; \
		FUNCTION_APP_NAME=$(FUNCTIONS_DEV); \
	elif [ "$$choice" = "2" ]; then \
		SELECTED_ENV="uat"; \
		FUNCTION_APP_NAME=$(FUNCTIONS_UAT); \
	else \
		echo "Invalid selection. Please run 'make all' again and choose a valid option."; \
		exit 1; \
	fi; \
	ZIP_FILE="$(ZIP_DIR)/$$SELECTED_ENV/corp-design-order-extract-$(PACKAGE_VERSION)-$(CURRENT_DATETIME).zip"; \
	echo "Selected Function: $$FUNCTION_APP_NAME"; \
	echo "Environment: $$SELECTED_ENV"; \
	echo "ZIP File: $$ZIP_FILE"; \
	$(MAKE) zip-build FUNCTION_APP_NAME=$$FUNCTION_APP_NAME ZIP_FILE=$$ZIP_FILE SELECTED_ENV=$$SELECTED_ENV

# Zip the source folder while excluding the version_zip folder
zip-build:
	@echo "Zipping source folder..."
	@zip -r $(ZIP_FILE) . -x "version_zip/*" ".venv/*" "__pycache__/*" "*.pyc" "*.pyo" ".git/*" ".DS_Store"
	@echo "Created zip: $(ZIP_FILE)"
	$(MAKE) deploy-durable-function FUNCTION_APP_NAME=$(FUNCTION_APP_NAME) ZIP_FILE=$(ZIP_FILE) SELECTED_ENV=$(SELECTED_ENV)

# Deploy the selected function
deploy-durable-function:
	@echo "Deploying Durable Function..."
	@func azure functionapp publish $(FUNCTION_APP_NAME) --python --build remote
	@echo "Deployment complete"
	$(MAKE) track-version FUNCTION_APP_NAME=$(FUNCTION_APP_NAME) ZIP_FILE=$(ZIP_FILE) SELECTED_ENV=$(SELECTED_ENV)

# Log the deployed version and track it properly
track-version:
	$(info Logging the deployed version...)
	echo "----------------------------------------" >> version_log.txt
	echo "Deployment Log - $$(date +"%Y-%m-%d %H:%M:%S")" >> version_log.txt
	echo "Environment: $(SELECTED_ENV)" >> version_log.txt
	echo "Function Name: $(FUNCTION_APP_NAME)" >> version_log.txt
	echo "Package Version: $(PACKAGE_VERSION)" >> version_log.txt
	echo "ZIP File: $(ZIP_FILE)" >> version_log.txt
	echo "----------------------------------------" >> version_log.txt
	$(info Version tracking updated in version_log.txt)

# Clean zip directories
clean:
	@echo "Removing version zip directory..."
	@rm -rf $(ZIP_DIR)
	@echo "Cleaned version zip files."

# Full pipeline: Select function, Zip, Deploy, and Track Version
all: prepare-dirs select-function

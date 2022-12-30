terraform {
  required_version = "~> 1.3.4"

  required_providers {
    sops = {
      source  = "carlpett/sops"
      version = "~> 0.5"
    }
  }

  backend "s3" {
    bucket = "terraform-states-flat"
    key    = "states/old-lambdas-cleaner/states.tfstate"
    region = "us-east-1"
  }
}

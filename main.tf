terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "6.8.0"
    }
  }
}

provider "google" {
  # Project ID can be moved to another file for security reasons
  credentials = file("~/gcp/terraform-creds.json")
  project     = "ace-charter-481619-j3"
  region      = "us-central1"
  zone        = "us-central1-a"
}

data "google_compute_network" "default" {
  name = "default"
}

resource "google_compute_address" "static_ip" {
  name   = "my-static-ip"
  region = "us-central1"
}

resource "google_compute_firewall" "allow_ssh" {
  name    = "allow-ssh"
  network = data.google_compute_network.default.name

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["ssh-allowed"]
}

resource "google_compute_firewall" "allow_http" {
  name    = "allow-http"
  network = data.google_compute_network.default.name

  allow {
    protocol = "tcp"
    ports    = ["80"]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["http-server"]
}

resource "google_compute_firewall" "allow_https" {
  name    = "allow-https"
  network = data.google_compute_network.default.name

  allow {
    protocol = "tcp"
    ports    = ["443"]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["https-server"]
}

resource "google_compute_instance" "vm_instance" {
  name         = "my-vm"
  machine_type = "e2-micro"

  boot_disk {
    initialize_params {
      image = "ubuntu-os-cloud/ubuntu-2204-lts"
    }
  }

  network_interface {
    network = "default"
    access_config {
      nat_ip = google_compute_address.static_ip.address
    }
  }

  tags = ["ssh-allowed", "http-server", "https-server"]

  metadata = {
    ssh-keys = "ubuntu:${file("~/.ssh/gcp_key.pub")}"
  }
  metadata_startup_script = "${file("install-docker-vm.sh")}"
}
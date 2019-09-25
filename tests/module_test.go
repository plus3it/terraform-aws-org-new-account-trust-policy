package testing

import (
	"io/ioutil"
	"log"
	"os"
	"testing"

	"github.com/gruntwork-io/terratest/modules/terraform"
)

func TestModule(t *testing.T) {
	files, err := ioutil.ReadDir("./")

	if err != nil {
		log.Fatal(err)
	}

	for _, f := range files {
		// look for directories with test cases in it
		if f.IsDir() && f.Name() != "vendor" {
			investigateDirectory(t, f)
		}
	}
}

func investigateDirectory(t *testing.T, directory os.FileInfo) {
	// check if a prereq directory exists
	prereqDir := directory.Name() + "/prereq/"
	if _, err := os.Stat(prereqDir); err == nil {
		prereqOptions := createTerraformOptions(prereqDir)
		defer terraform.Destroy(t, prereqOptions)
		terraform.InitAndApply(t, prereqOptions)
	}

	// run terraform code for test case
	terraformOptions := createTerraformOptions(directory.Name())
	defer terraform.Destroy(t, terraformOptions)
	terraform.InitAndApply(t, terraformOptions)
}

func createTerraformOptions(directory string) *terraform.Options {
	terraformOptions := &terraform.Options{
		TerraformDir: directory,
		NoColor:      true,
	}

	return terraformOptions
}

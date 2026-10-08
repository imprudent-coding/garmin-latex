import java.io.File

plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
}

// L'UUID dell'app Connect IQ è condiviso con garmin/manifest.xml.
val watchAppId = File(rootDir, "../shared/app-id.txt").readText().trim()
// "android-v1.2.3" -> "1.2.3" (tag della release), altrimenti versione di sviluppo
val tagVersion = (System.getenv("GITHUB_REF_NAME") ?: "").removePrefix("android-v").takeIf { it.matches(Regex("""\d+\.\d+\.\d+.*""")) }
val buildNumber = (System.getenv("GITHUB_RUN_NUMBER") ?: "1").toInt()

// Firma: keystore fornito dalla CI (secrets) tramite variabili d'ambiente.
val keystorePath: String? = System.getenv("ANDROID_KEYSTORE_PATH")
val hasSigning = keystorePath != null && File(keystorePath).exists() &&
    !System.getenv("ANDROID_KEYSTORE_PASSWORD").isNullOrEmpty()

android {
    namespace = "io.github.imprudentcoding.garminlatex"
    compileSdk = 36

    defaultConfig {
        applicationId = "io.github.imprudentcoding.garminlatex"
        minSdk = 26
        targetSdk = 36
        versionCode = buildNumber
        versionName = tagVersion ?: "0.1.0-dev"
        buildConfigField("String", "WATCH_APP_ID", "\"$watchAppId\"")
        buildConfigField("String", "DEFAULT_REPO", "\"imprudent-coding/garmin-latex\"")
        buildConfigField("int", "BUNDLE_SCHEMA", "1")
    }

    signingConfigs {
        if (hasSigning) {
            create("release") {
                storeFile = File(keystorePath!!)
                storePassword = System.getenv("ANDROID_KEYSTORE_PASSWORD")
                keyAlias = System.getenv("ANDROID_KEY_ALIAS") ?: "notes"
                keyPassword = System.getenv("ANDROID_KEY_PASSWORD") ?: System.getenv("ANDROID_KEYSTORE_PASSWORD")
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            if (hasSigning) {
                signingConfig = signingConfigs.getByName("release")
            }
        }
        debug {
            applicationIdSuffix = ".debug"
            versionNameSuffix = "-debug"
        }
    }

    sourceSets {
        // font bitmap dell'orologio: usati per l'anteprima delle pagine
        getByName("main").assets.srcDir(File(rootDir, "../shared/font/generated"))
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    packaging {
        resources.excludes += "/META-INF/{AL2.0,LGPL2.1}"
    }
    testOptions {
        unitTests.isReturnDefaultValues = true
    }
}

kotlin {
    compilerOptions {
        jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17)
    }
}

dependencies {
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.activity.compose)
    implementation(libs.androidx.lifecycle.runtime.compose)
    implementation(libs.androidx.lifecycle.viewmodel.compose)
    implementation(libs.androidx.lifecycle.service)
    implementation(libs.androidx.navigation.compose)
    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.compose.ui)
    implementation(libs.androidx.compose.ui.graphics)
    implementation(libs.androidx.compose.ui.tooling.preview)
    implementation(libs.androidx.compose.material3)
    implementation(libs.androidx.compose.material.icons)
    implementation(libs.androidx.work.runtime.ktx)
    implementation(libs.kotlinx.coroutines.android)
    implementation(libs.connectiq.sdk) { artifact { type = "aar" } }

    testImplementation(libs.junit)
    testImplementation(libs.org.json)
}

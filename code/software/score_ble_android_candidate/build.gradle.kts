plugins {
    id("com.android.application") version "8.7.3" apply false
    id("org.jetbrains.kotlin.android") version "2.0.21" apply false
}
allprojects {
    providers.gradleProperty("candidateBuildDir").orNull?.let { base ->
        layout.buildDirectory.set(file("$base/${project.name}"))
    }
}

"use client"

import { useState, useRef } from "react"
import { useRouter } from "next/navigation"
import { Upload, FileText, X } from "lucide-react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"

export default function Home() {
  const [file, setFile] = useState<File | null>(null)
  const [isProcessing, setIsProcessing] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const router = useRouter()

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = event.target.files?.[0]

    if (!selectedFile) return

    // Validate that it's a PDF
    if (selectedFile.type !== "application/pdf") {
      toast.error("Invalid file type", {
        description: "Please upload a PDF file"
      })
      return
    }

    setFile(selectedFile)
    toast.success("File uploaded", {
      description: `${selectedFile.name} ready to process`
    })
  }

  const handleUploadClick = () => {
    fileInputRef.current?.click()
  }

  const handleRemoveFile = () => {
    setFile(null)
    if (fileInputRef.current) {
      fileInputRef.current.value = ""
    }
    toast.info("File removed")
  }

  const handleProcess = async () => {
    if (!file) return

    setIsProcessing(true)

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5001"

      // Step 1: Initiate multipart upload
      console.log("Initiating multipart upload for:", file.name)
      const initiateResponse = await fetch(`${apiUrl}/initiate-upload`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          filename: file.name,
          content_type: file.type,
        }),
      })

      if (!initiateResponse.ok) {
        const errorData = await initiateResponse.json()
        throw new Error(errorData.message || `Failed to initiate upload: ${initiateResponse.statusText}`)
      }

      const { upload_id, s3_key, s3_bucket } = await initiateResponse.json()
      console.log("Upload initiated:", { upload_id, s3_key })

      // Step 2: Upload file in chunks (5MB each)
      const chunkSize = 5 * 1024 * 1024 // 5MB
      const chunks = Math.ceil(file.size / chunkSize)
      const uploadedParts: { PartNumber: number; ETag: string }[] = []

      console.log(`Uploading ${chunks} chunks...`)

      for (let partNumber = 1; partNumber <= chunks; partNumber++) {
        const start = (partNumber - 1) * chunkSize
        const end = Math.min(start + chunkSize, file.size)
        const chunk = file.slice(start, end)

        console.log(`Uploading part ${partNumber}/${chunks} (${chunk.size} bytes)`)

        // Get presigned URL for this part
        const partUrlResponse = await fetch(`${apiUrl}/get-part-url`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            upload_id,
            s3_key,
            part_number: partNumber,
          }),
        })

        if (!partUrlResponse.ok) {
          throw new Error(`Failed to get part URL: ${partUrlResponse.statusText}`)
        }

        const { upload_url } = await partUrlResponse.json()

        // Upload the chunk
        const uploadResponse = await fetch(upload_url, {
          method: "PUT",
          body: chunk,
        })

        if (!uploadResponse.ok) {
          throw new Error(`Failed to upload part ${partNumber}: ${uploadResponse.statusText}`)
        }

        // Get ETag from response headers
        const etag = uploadResponse.headers.get("ETag")
        if (!etag) {
          throw new Error(`No ETag returned for part ${partNumber}`)
        }

        uploadedParts.push({ PartNumber: partNumber, ETag: etag })
        console.log(`Part ${partNumber} uploaded, ETag: ${etag}`)
      }

      // Step 3: Complete the multipart upload
      console.log("Completing multipart upload...")
      const completeResponse = await fetch(`${apiUrl}/complete-upload`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          upload_id,
          s3_key,
          parts: uploadedParts,
        }),
      })

      if (!completeResponse.ok) {
        const errorData = await completeResponse.json()
        throw new Error(errorData.message || `Failed to complete upload: ${completeResponse.statusText}`)
      }

      console.log("File uploaded to S3:", s3_key)

      // Step 4: Parse the document using the S3 location
      const parseRequest = {
        s3_bucket,
        s3_key,
        gap_factor: 1.5,
      }

      console.log("Sending parse request:", parseRequest)
      const parseResponse = await fetch(`${apiUrl}/parse`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(parseRequest),
      })

      if (!parseResponse.ok) {
        const errorData = await parseResponse.json()
        throw new Error(errorData.message || `Parse failed: ${parseResponse.statusText}`)
      }

      const data = await parseResponse.json()
      console.log("Received parse response:", data)

      // Store the form data in localStorage to pass to the form page
      localStorage.setItem("formData", JSON.stringify(data.form))

      // Redirect to the form fields display route
      router.push("/form")
    } catch (error) {
      console.error("Error processing file:", error)
      toast.error("Processing failed", {
        description: error instanceof Error ? error.message : "Failed to process the file"
      })
      setIsProcessing(false)
    }
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-background p-8">
      <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle>Upload Form</CardTitle>
            <CardDescription>
              Select a PDF file to parse and analyze
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex flex-col items-center justify-center gap-4 py-4">
              {file ? (
                <div className="flex items-center gap-3 rounded-lg border border-border bg-muted/50 px-4 py-3 w-full">
                  <FileText className="h-5 w-5 text-muted-foreground flex-shrink-0" />
                  <span className="text-sm font-medium truncate flex-1">{file.name}</span>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-6 w-6 flex-shrink-0"
                    onClick={handleRemoveFile}
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </div>
              ) : (
                <div className="flex flex-col items-center gap-2 text-muted-foreground py-8">
                  <Upload className="h-12 w-12" />
                  <p className="text-sm">No file uploaded yet</p>
                </div>
              )}
            </div>
          </CardContent>
          <CardFooter className="flex gap-2">
            <input
              ref={fileInputRef}
              type="file"
              accept="application/pdf"
              onChange={handleFileSelect}
              className="hidden"
            />
            <Button
              type="button"
              variant="outline"
              onClick={handleUploadClick}
              disabled={!!file}
              className="flex-1"
            >
              <Upload className="mr-2 h-4 w-4" />
              Upload File
            </Button>
            <Button
              type="button"
              onClick={handleProcess}
              disabled={!file || isProcessing}
              className="flex-1"
            >
              {isProcessing ? (
                <>
                  <svg
                    className="mr-2 h-4 w-4 animate-spin"
                    xmlns="http://www.w3.org/2000/svg"
                    fill="none"
                    viewBox="0 0 24 24"
                  >
                    <circle
                      className="opacity-25"
                      cx="12"
                      cy="12"
                      r="10"
                      stroke="currentColor"
                      strokeWidth="4"
                    />
                    <path
                      className="opacity-75"
                      fill="currentColor"
                      d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                    />
                  </svg>
                  Processing...
                </>
              ) : (
                "Process File"
              )}
            </Button>
          </CardFooter>
        </Card>
    </div>
  )
}

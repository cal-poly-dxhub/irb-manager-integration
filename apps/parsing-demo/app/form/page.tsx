"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { ArrowLeft, FileText, Table as TableIcon } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { toast } from "sonner"

interface ParagraphField {
  type: "paragraph"
  id: string
  title: string
  content: string
  page: number
  instructions?: string
}

interface TableField {
  type: "table"
  id: string
  title: string
  content: string[][]
  headers: string[]
  page: number
  instructions?: string
}

interface GroupedField {
  type: "grouped"
  id: string
  title: string
  section_number?: string
  content: FormMember[]
  page: number
  instructions?: string
}

type Field = ParagraphField | TableField | GroupedField

interface FormMember {
  field: Field
}

interface Form {
  members: FormMember[]
}

export default function FormPage() {
  const [form, setForm] = useState<Form | null>(null)
  const [editedFields, setEditedFields] = useState<Map<string, Field>>(new Map())
  const router = useRouter()

  useEffect(() => {
    // Load form data from localStorage
    const formDataString = localStorage.getItem("formData")
    if (!formDataString) {
      toast.error("No form data found", {
        description: "Please upload and process a file first"
      })
      router.push("/")
      return
    }

    try {
      const formData = JSON.parse(formDataString)
      setForm(formData)
    } catch (error) {
      console.error("Error parsing form data:", error)
      toast.error("Invalid form data")
      router.push("/")
    }
  }, [router])

  // Recursively find a field by ID in the form structure
  const findField = (members: FormMember[], id: string): Field | null => {
    for (const member of members) {
      if (member.field.id === id) {
        return member.field
      }
      if (member.field.type === "grouped") {
        const found = findField(member.field.content, id)
        if (found) return found
      }
    }
    return null
  }

  const handleParagraphEdit = (id: string, newContent: string) => {
    if (!form) return

    const updated = new Map(editedFields)
    const field = findField(form.members, id)
    if (field && field.type === "paragraph") {
      updated.set(id, { ...field, content: newContent })
      setEditedFields(updated)
    }
  }

  const handleTableEdit = (id: string, rowIndex: number, colIndex: number, newValue: string) => {
    if (!form) return

    const updated = new Map(editedFields)
    const field = findField(form.members, id)
    if (field && field.type === "table") {
      const newContent = field.content.map((row, ri) =>
        ri === rowIndex
          ? row.map((cell, ci) => (ci === colIndex ? newValue : cell))
          : row
      )
      updated.set(id, { ...field, content: newContent })
      setEditedFields(updated)
    }
  }

  const getField = (field: Field): Field => {
    return editedFields.get(field.id) || field
  }

  // Recursive function to count total fields (including nested)
  const countFields = (members: FormMember[]): number => {
    return members.reduce((count, member) => {
      if (member.field.type === "grouped") {
        return count + countFields(member.field.content)
      }
      return count + 1
    }, 0)
  }

  // Render a single field (paragraph, table, or grouped)
  const renderField = (field: Field, depth: number = 0): JSX.Element | null => {
    const currentField = getField(field)

    if (currentField.type === "paragraph") {
      return (
        <Card style={{ marginLeft: `${depth * 16}px` }}>
          <CardHeader>
            <div className="flex items-center gap-2">
              <FileText className="h-4 w-4 text-muted-foreground" />
              <CardTitle className="text-base">
                {currentField.title}
              </CardTitle>
              <span className="ml-auto text-xs text-muted-foreground">
                Page {field.page}
              </span>
            </div>
            {currentField.instructions && (
              <CardDescription className="text-xs mt-1">
                {currentField.instructions}
              </CardDescription>
            )}
          </CardHeader>
          <CardContent>
            <textarea
              value={currentField.content}
              onChange={(e) => handleParagraphEdit(field.id, e.target.value)}
              className="w-full min-h-[100px] rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
            />
          </CardContent>
        </Card>
      )
    }

    if (currentField.type === "table") {
      return (
        <Card style={{ marginLeft: `${depth * 16}px` }}>
          <CardHeader>
            <div className="flex items-center gap-2">
              <TableIcon className="h-4 w-4 text-muted-foreground" />
              <CardTitle className="text-base">
                {currentField.title}
              </CardTitle>
              <span className="ml-auto text-xs text-muted-foreground">
                Page {field.page}
              </span>
            </div>
            {currentField.instructions && (
              <CardDescription className="text-xs mt-1">
                {currentField.instructions}
              </CardDescription>
            )}
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full border-collapse">
                {currentField.headers && currentField.headers.length > 0 && (
                  <thead>
                    <tr className="bg-muted/50">
                      {currentField.headers.map((header, index) => (
                        <th key={index} className="border border-border p-2 text-left text-sm font-medium">
                          {header}
                        </th>
                      ))}
                    </tr>
                  </thead>
                )}
                <tbody>
                  {currentField.content.map((row, rowIndex) => (
                    <tr key={rowIndex}>
                      {row.map((cell, colIndex) => (
                        <td
                          key={colIndex}
                          className="border border-border p-2"
                        >
                          <input
                            type="text"
                            value={cell}
                            onChange={(e) =>
                              handleTableEdit(field.id, rowIndex, colIndex, e.target.value)
                            }
                            className="w-full bg-transparent text-sm focus:outline-none focus:ring-1 focus:ring-ring rounded px-1"
                          />
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )
    }

    if (currentField.type === "grouped") {
      return (
        <Card style={{ marginLeft: `${depth * 16}px` }} className="border-2 border-primary/20">
          <CardHeader>
            <div className="flex items-center gap-2">
              <FileText className="h-4 w-4 text-primary" />
              <CardTitle className="text-base">
                {currentField.title}
                {currentField.section_number && ` (Section ${currentField.section_number})`}
              </CardTitle>
              <span className="ml-auto text-xs text-muted-foreground">
                Page {field.page}
              </span>
            </div>
            <CardDescription>
              {countFields(currentField.content)} field{countFields(currentField.content) !== 1 ? "s" : ""} in this group
              {currentField.instructions && ` • ${currentField.instructions}`}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {currentField.content.map((member) => (
              <div key={member.field.id}>
                {renderField(member.field, depth + 1)}
              </div>
            ))}
          </CardContent>
        </Card>
      )
    }

    // Fallback for unknown field types
    return (
      <Card style={{ marginLeft: `${depth * 16}px` }} className="border-2 border-yellow-500/50 bg-yellow-50">
        <CardHeader>
          <CardTitle className="text-sm text-yellow-800">Unknown Field Type: {currentField.type}</CardTitle>
        </CardHeader>
        <CardContent>
          <pre className="text-xs overflow-auto">{JSON.stringify(currentField, null, 2)}</pre>
        </CardContent>
      </Card>
    )
  }

  if (!form) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="text-muted-foreground">Loading...</div>
      </div>
    )
  }

  const totalFields = countFields(form.members)

  console.log("Rendering form with members:", form.members.length)
  console.log("Total fields:", totalFields)
  console.log("Full members array:", form.members)

  return (
    <div className="min-h-screen bg-background p-8">
      <div className="mx-auto max-w-4xl space-y-6">
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => router.push("/")}
          >
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <div className="space-y-1">
            <h1 className="text-3xl font-bold tracking-tight">Form Fields</h1>
            <p className="text-muted-foreground">
              {form.members.length} top-level member{form.members.length !== 1 ? "s" : ""} ({totalFields} total field{totalFields !== 1 ? "s" : ""})
            </p>
          </div>
        </div>

        {/* Debug info card */}
        <Card className="bg-muted/30">
          <CardHeader>
            <CardTitle className="text-sm">Debug Info</CardTitle>
          </CardHeader>
          <CardContent>
            <pre className="text-xs overflow-auto max-h-40">
              {JSON.stringify(form, null, 2)}
            </pre>
          </CardContent>
        </Card>

        <div className="space-y-4">
          {!form.members || form.members.length === 0 ? (
            <Card>
              <CardContent className="p-6">
                <p className="text-muted-foreground">No members found in form data</p>
              </CardContent>
            </Card>
          ) : (
            form.members.map((member, idx) => {
              console.log(`Rendering member ${idx}:`, member)
              console.log(`Field type: ${member.field?.type}, ID: ${member.field?.id}`)

              const renderedField = renderField(member.field)
              console.log(`Rendered result for member ${idx}:`, renderedField)

              return (
                <div key={member.field?.id || `member-${idx}`}>
                  {renderedField || (
                    <Card className="bg-destructive/10">
                      <CardContent className="p-4">
                        <p className="text-sm text-destructive">Failed to render field type: {member.field?.type}</p>
                        <pre className="text-xs mt-2">{JSON.stringify(member, null, 2)}</pre>
                      </CardContent>
                    </Card>
                  )}
                </div>
              )
            })
          )}
        </div>
      </div>
    </div>
  )
}

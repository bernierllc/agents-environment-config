# Tailwind CSS Styling Standards

## Light Theme Only (MANDATORY)

All components must use light theme only. Dark theme elements are prohibited.

```typescript
// ✅ REQUIRED: Light theme classes only
<div className="min-h-screen bg-gray-50 space-y-6 p-6">
  <Card className="bg-white border-gray-200 shadow-sm">
    <CardHeader className="pb-4">
      <CardTitle className="text-gray-900">Heading</CardTitle>
    </CardHeader>
    <CardContent>
      <p className="text-gray-700">Body text</p>
    </CardContent>
  </Card>
</div>
```

## Color Palette (MUST USE)

### Background Colors
- `bg-gray-50` - Main page backgrounds
- `bg-white` - Cards and panels
- `bg-blue-50` - Info sections
- `bg-green-50` - Success sections
- `bg-yellow-50` - Warning sections
- `bg-red-50` - Error sections

### Text Colors
- `text-gray-900` - Headings and main text
- `text-gray-700` - Body text and labels
- `text-gray-600` - Secondary information
- `text-gray-500` - Placeholder and help text
- `text-blue-600` - Links and interactive elements

### Border Colors
- `border-gray-200` - All card and component borders
- `border-blue-200` - Info section borders
- `border-green-200` - Success section borders
- `border-yellow-200` - Warning section borders
- `border-red-200` - Error section borders

## Component Patterns

### Card Components
```typescript
<Card className="border-gray-200 shadow-sm hover:shadow-md transition-shadow">
  <CardHeader className="pb-4">
    <CardTitle className="text-gray-900">Title</CardTitle>
  </CardHeader>
  <CardContent className="space-y-4">
    <p className="text-gray-700">Content</p>
  </CardContent>
</Card>
```

### Button Components
```typescript
// Primary buttons
<Button className="bg-blue-600 hover:bg-blue-700 text-white transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500">
  Primary Action
</Button>

// Secondary buttons
<Button variant="outline" className="border-gray-300 text-gray-700 hover:bg-gray-50">
  Secondary Action
</Button>
```

### Form Elements
```typescript
<Input 
  className="border-gray-300 text-gray-900 placeholder-gray-500 focus:border-blue-500 focus:ring-blue-500 focus:ring-2"
  placeholder="Enter text..."
/>
```

## Interactive States

### Hover Effects
- `hover:shadow-md` - Enhanced shadow for cards
- `hover:bg-blue-700` - Button hover states
- `transition-shadow` - Smooth transitions
- `transition-colors` - Color transitions

### Focus States
- `focus:border-blue-500` - Form element focus
- `focus:ring-blue-500` - Focus ring
- `focus:ring-2` - Ring width
- `focus:outline-none` - Remove default outline

## Spacing System

### Vertical Spacing
- `space-y-6` - Large spacing between major sections
- `space-y-4` - Medium spacing between related elements
- `space-y-3` - Small spacing between grouped items

### Padding
- `p-6` - Card padding
- `p-4` - Section padding
- `p-3` - Component padding

## Prohibited Patterns

❌ **NEVER USE:**
- Dark theme elements (`bg-gray-900`, `text-white`)
- Mixed themes
- Random colors without semantic meaning

## References
- **Architecture**: See `general/architecture.mdc`
- **TypeScript**: See `languages/typescript/typing-standards.mdc`
